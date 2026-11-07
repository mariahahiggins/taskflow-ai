"""API integration checks using disposable SQLite databases, never taskflow.db."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import database
from backend.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EMPLOYEE = {"name": "Alex Johnson", "available_hours": 40, "experience_level": "Mid"}
TASK = {
    "title": "Prepare report",
    "estimated_hours": 10,
    "deadline": "2026-11-05",
    "priority": "High",
    "difficulty": "Medium",
}


class EmployeeTaskAPITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="taskflow api ")
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "taskflow.db"
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.executescript(
                (PROJECT_ROOT / "backend" / "schema.sql").read_text(encoding="utf-8")
            )
        self.enterContext(patch.object(database, "DATABASE_PATH", self.database_path))
        calendar = self.enterContext(patch("backend.main.date"))
        calendar.today.return_value = date(2026, 11, 6)
        self.client = self.enterContext(TestClient(app))

    def create_employee(self, **changes):
        response = self.client.post("/employees", json={**EMPLOYEE, **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def create_task(self, **changes):
        response = self.client.post("/tasks", json={**TASK, **changes})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_status_documentation_and_all_data_routes(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/docs").status_code, 200)
        specification = self.client.get("/openapi.json").json()
        expected = {
            "/employees": {"get", "post"},
            "/employees/{id}": {"get", "put"},
            "/tasks": {"get", "post"},
            "/tasks/{id}": {"get", "put"},
            "/employees/{id}/workload": {"get"},
            "/workloads": {"get"},
        }
        for path, methods in expected.items():
            self.assertTrue(methods.issubset(specification["paths"][path]))

    def test_empty_lists(self):
        for path in ("/employees", "/tasks"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), [])

    def test_create_list_and_retrieve_employee(self):
        employee = self.create_employee(name=" Alex Johnson ")
        self.assertEqual(employee["name"], "Alex Johnson")
        self.assertGreater(employee["employee_id"], 0)
        self.assertEqual(
            self.client.get(f'/employees/{employee["employee_id"]}').json(), employee
        )
        self.assertEqual(self.client.get("/employees").json(), [employee])

    def test_update_employee_and_allow_zero_availability(self):
        employee = self.create_employee()
        values = {**EMPLOYEE, "available_hours": 0, "experience_level": "Senior"}
        response = self.client.put(f'/employees/{employee["employee_id"]}', json=values)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {**values, "employee_id": employee["employee_id"]})

    def test_reject_bad_employee_input_without_writing(self):
        cases = [
            {"name": "   "}, {"available_hours": -1}, {"available_hours": True},
            {"experience_level": "Expert"}, {"employee_id": 99},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(
                    self.client.post("/employees", json={**EMPLOYEE, **changes}).status_code,
                    422,
                )
        self.assertEqual(self.client.get("/employees").json(), [])

    def test_missing_records_are_404_and_bad_path_ids_are_422(self):
        for collection in ("employees", "tasks"):
            self.assertEqual(self.client.get(f"/{collection}/999").status_code, 404)
            for identifier in ("0", "-1", "abc"):
                with self.subTest(collection=collection, identifier=identifier):
                    self.assertEqual(
                        self.client.get(f"/{collection}/{identifier}").status_code, 422
                    )

    def test_task_defaults_and_date_serialization(self):
        task = self.create_task()
        self.assertEqual(task["status"], "Active")
        self.assertIsNone(task["employee_id"])
        self.assertEqual(task["deadline"], "2026-11-05")
        self.assertEqual(self.client.get(f'/tasks/{task["task_id"]}').json(), task)
        self.assertEqual(self.client.get("/tasks").json(), [task])

    def test_create_task_assigned_to_existing_employee(self):
        employee = self.create_employee()
        task = self.create_task(employee_id=employee["employee_id"])
        self.assertEqual(task["employee_id"], employee["employee_id"])

    def test_reject_unknown_assignment_without_saving_task(self):
        response = self.client.post("/tasks", json={**TASK, "employee_id": 999})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "The assigned employee does not exist.")
        self.assertEqual(self.client.get("/tasks").json(), [])

    def test_reject_bad_task_input_without_writing(self):
        cases = [
            {"title": "   "}, {"estimated_hours": 0}, {"estimated_hours": -2},
            {"estimated_hours": True}, {"deadline": "2026-02-30"},
            {"priority": "Urgent"}, {"difficulty": "Difficult"},
            {"status": "Pending"}, {"employee_id": 0}, {"employee_id": True},
            {"task_id": 99},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertEqual(
                    self.client.post("/tasks", json={**TASK, **changes}).status_code, 422
                )
        self.assertEqual(self.client.get("/tasks").json(), [])

    def test_task_update_can_complete_reassign_and_unassign(self):
        first = self.create_employee()
        second = self.create_employee(name="Taylor Kim")
        task = self.create_task(employee_id=first["employee_id"])
        values = {**TASK, "status": "Completed", "employee_id": second["employee_id"]}
        response = self.client.put(f'/tasks/{task["task_id"]}', json=values)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "Completed")
        self.assertEqual(response.json()["employee_id"], second["employee_id"])
        response = self.client.put(
            f'/tasks/{task["task_id"]}', json={**values, "employee_id": None}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["employee_id"])
        self.assertEqual(response.json()["status"], "Completed")

    def test_incomplete_put_does_not_reset_existing_data(self):
        employee = self.create_employee()
        task = self.create_task(employee_id=employee["employee_id"], status="Completed")
        self.assertEqual(task["status"], "Completed")
        employee_path = f'/employees/{employee["employee_id"]}'
        task_path = f'/tasks/{task["task_id"]}'
        self.assertEqual(self.client.put(employee_path, json={"name": "Changed"}).status_code, 422)
        for values in ({**TASK}, {**TASK, "status": "Active"}, {**TASK, "employee_id": None}):
            self.assertEqual(self.client.put(task_path, json=values).status_code, 422)
        self.assertEqual(self.client.get(employee_path).json(), employee)
        self.assertEqual(self.client.get(task_path).json(), task)

    def test_invalid_assignment_update_preserves_existing_record(self):
        employee = self.create_employee()
        task = self.create_task(employee_id=employee["employee_id"])
        values = {**TASK, "title": "Changed", "status": "Completed", "employee_id": 999}
        task_path = f'/tasks/{task["task_id"]}'
        self.assertEqual(self.client.put(task_path, json=values).status_code, 400)
        self.assertEqual(self.client.get(task_path).json(), task)

    def test_update_missing_records_does_not_create_them(self):
        self.assertEqual(self.client.put("/employees/999", json=EMPLOYEE).status_code, 404)
        values = {**TASK, "status": "Active", "employee_id": None}
        self.assertEqual(self.client.put("/tasks/999", json=values).status_code, 404)
        self.assertEqual(self.client.get("/employees").json(), [])
        self.assertEqual(self.client.get("/tasks").json(), [])

    def test_records_persist_for_new_clients(self):
        employee = self.create_employee()
        task = self.create_task(employee_id=employee["employee_id"])
        with TestClient(app) as other_client:
            self.assertEqual(other_client.get("/employees").json(), [employee])
            self.assertEqual(other_client.get("/tasks").json(), [task])
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)

    def test_names_are_stored_as_data_not_sql(self):
        name = "Robert'); DROP TABLE employees;--"
        employee = self.create_employee(name=name)
        self.assertEqual(employee["name"], name)
        self.assertEqual(len(self.client.get("/employees").json()), 1)
        self.assertEqual(self.client.get("/tasks").status_code, 200)

    def test_missing_database_reports_503_without_creating_a_file(self):
        missing = self.database_path.with_name("not-initialized.db")
        with patch.object(database, "DATABASE_PATH", missing):
            for path in ("/employees", "/employees/1/workload", "/workloads"):
                with self.subTest(path=path):
                    self.assertEqual(self.client.get(path).status_code, 503)
            self.assertEqual(self.client.get("/health").status_code, 200)
            self.assertFalse(missing.exists())

    def test_individual_workload_counts_active_assigned_tasks_and_conflicts(self):
        employee_id = self.create_employee(available_hours=5)["employee_id"]
        other_id = self.create_employee(name="Taylor Kim")["employee_id"]
        self.create_task(employee_id=employee_id, estimated_hours=2)
        self.create_task(
            employee_id=employee_id, estimated_hours=3, deadline="2026-11-06"
        )
        self.create_task(employee_id=employee_id, status="Completed")
        self.create_task(employee_id=other_id)
        self.create_task()

        response = self.client.get(f"/employees/{employee_id}/workload")
        self.assertEqual(response.status_code, 200, response.text)
        summary = response.json()
        self.assertEqual(summary["employee_id"], employee_id)
        self.assertEqual(summary["outstanding_hours"], 5)
        self.assertEqual(summary["active_task_count"], 2)
        self.assertEqual(summary["overdue_task_count"], 1)
        self.assertEqual(summary["within_1_week_count"], 1)
        self.assertAlmostEqual(summary["one_week_utilization"], 5 / 6 * 100)
        self.assertAlmostEqual(summary["two_week_utilization"], 5 / 11 * 100)
        self.assertEqual(summary["deadline_conflicts"], [
            {
                "deadline": "2026-11-05",
                "required_hours": 2,
                "available_hours": 0,
                "shortfall_hours": 2,
                "type": "overdue",
            },
            {
                "deadline": "2026-11-06",
                "required_hours": 5,
                "available_hours": 1,
                "shortfall_hours": 4,
                "type": "capacity",
            },
        ])

    def test_workload_requires_a_valid_existing_employee(self):
        missing = self.client.get("/employees/999/workload")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["detail"], "Employee not found.")
        self.assertEqual(self.client.get("/employees/0/workload").status_code, 422)

    def test_team_workload_includes_fairness_and_unassigned_tasks(self):
        assigned_id = self.create_employee()["employee_id"]
        idle_id = self.create_employee(name="Taylor Kim")["employee_id"]
        zero_capacity_id = self.create_employee(
            name="Riley Chen", available_hours=0
        )["employee_id"]
        assigned = self.create_task(
            employee_id=assigned_id, deadline="2026-11-10", difficulty="Hard"
        )
        unassigned = self.create_task(estimated_hours=4, difficulty="Hard")
        self.create_task(employee_id=idle_id, status="Completed", difficulty="Hard")
        self.create_task(status="Completed")

        response = self.client.get("/workloads")
        self.assertEqual(response.status_code, 200, response.text)
        summary = response.json()
        self.assertEqual(summary["total_employees"], 3)
        self.assertEqual(summary["active_tasks"], 1)
        self.assertEqual(summary["unassigned_tasks"], 1)
        self.assertEqual(summary["outstanding_hours"], 10)
        self.assertEqual(summary["overdue_tasks"], 0)
        self.assertEqual(summary["total_deadline_conflicts"], 0)
        self.assertEqual(summary["upcoming_deadlines"], [unassigned, assigned])
        employees = {item["employee_id"]: item for item in summary["employees"]}
        self.assertIsNone(employees[zero_capacity_id]["one_week_utilization"])
        self.assertIsNone(employees[zero_capacity_id]["two_week_utilization"])
        fairness = summary["fairness"]
        self.assertAlmostEqual(fairness["one_week_utilization_spread"], 10 / 48 * 100)
        self.assertAlmostEqual(fairness["two_week_utilization_spread"], 10 / 88 * 100)
        counts = {
            str(assigned_id): {"count": 1, "hours": 10},
            str(idle_id): {"count": 0, "hours": 0},
            str(zero_capacity_id): {"count": 0, "hours": 0},
        }
        self.assertEqual(fairness["high_priority_tasks"], counts)
        self.assertEqual(fairness["difficult_tasks"], counts)

    def test_empty_team_workload(self):
        response = self.client.get("/workloads")
        self.assertEqual(response.status_code, 200, response.text)
        summary = response.json()
        self.assertEqual(summary["total_employees"], 0)
        self.assertEqual(summary["active_tasks"], 0)
        self.assertEqual(summary["unassigned_tasks"], 0)
        self.assertEqual(summary["employees"], [])
        self.assertEqual(summary["upcoming_deadlines"], [])
        self.assertEqual(summary["fairness"]["high_priority_tasks"], {})
        self.assertIsNone(summary["fairness"]["one_week_utilization_spread"])

    def test_workload_handles_latest_valid_deadline(self):
        employee_id = self.create_employee()["employee_id"]
        self.create_task(employee_id=employee_id, deadline=date.max.isoformat())
        response = self.client.get(f"/employees/{employee_id}/workload")
        self.assertEqual(response.status_code, 200, response.text)
        summary = response.json()
        self.assertEqual(summary["outstanding_hours"], 10)
        self.assertEqual(summary["after_2_weeks_count"], 1)
        self.assertEqual(summary["one_week_utilization"], 0)
        self.assertEqual(summary["deadline_conflicts"], [])


if __name__ == "__main__":
    unittest.main()
