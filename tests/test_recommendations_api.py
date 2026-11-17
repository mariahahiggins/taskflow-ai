"""Integration tests for TaskFlow AI recommendation endpoints."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from google.genai import errors as genai_errors

from backend import database
from backend.main import app


PROJECT_ROOT = Path(__file__).resolve().parents[1]

EMPLOYEE = {
    "name": "Alex Johnson",
    "available_hours": 40,
    "experience_level": "Senior",
}

TASK = {
    "title": "Prepare report",
    "estimated_hours": 10,
    "deadline": "2026-11-13",
    "priority": "High",
    "difficulty": "Easy",
}

class TestGenerateRecommendationsAPI(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="taskflow recommendations ")
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "taskflow.db"

        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.executescript(
                (PROJECT_ROOT / "backend" / "schema.sql").read_text(
                    encoding="utf-8"
                )
            )
        self.enterContext(
            patch.object(database, "DATABASE_PATH", self.database_path)
        )
        calendar = self.enterContext(patch("backend.main.date"))
        calendar.today.return_value = date(2026, 11, 9)
        self.client = self.enterContext(TestClient(app))

    def create_employee(self, **changes):
        response = self.client.post(
            "/employees",
            json={**EMPLOYEE, **changes}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def create_task(self, **changes):
        response = self.client.post(
            "/tasks",
            json={**TASK, **changes}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def mock_gemini(self, recommendations):
        return patch(
            "backend.main.ai_integration.generate_task_recommendations",
            return_value={"recommendations": recommendations}
        )

    def test_valid_recommendation(self):
        employee = self.create_employee()
        task = self.create_task()
        recommendation = {
            "task_id": task["task_id"],
            "employee_id": employee["employee_id"],
            "reason": "The employee has suitable experience."
        }
        with self.mock_gemini([recommendation]) as gemini:
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(len(result["recommendations"]), 1)
        gemini.assert_called_once()
        saved_task = self.client.get(
            f'/tasks/{task["task_id"]}'
        ).json()
        self.assertIsNone(saved_task["employee_id"])

    def test_no_employees_skips_gemini(self):
        self.create_task()
        with self.mock_gemini([]) as gemini:
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"recommendations": []})
        gemini.assert_not_called()

    def test_no_active_tasks_skips_gemini(self):
        self.create_employee()
        task = self.create_task()
        values = {
            key: value
            for key, value in task.items()
            if key != "task_id"
        }
        response = self.client.put(
            f'/tasks/{task["task_id"]}',
            json={**values, "status": "Completed"}
        )
        self.assertEqual(response.status_code, 200)
        with self.mock_gemini([]) as gemini:
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"recommendations": []})
        gemini.assert_not_called()

    def test_completed_task_recommendation_rejected(self):
        employee = self.create_employee()
        task = self.create_task()
        values = {
            key: value
            for key, value in task.items()
            if key != "task_id"
        }
        self.client.put(
            f'/tasks/{task["task_id"]}',
            json={**values, "status": "Completed"}
        )
        self.create_task(title="Another task")
        recommendation = {
            "task_id": task["task_id"],
            "employee_id": employee["employee_id"],
            "reason": "Incorrect recommendation."
        }
        with self.mock_gemini([recommendation]):
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 502)
        self.assertIn("not eligible", response.json()["detail"])

    def test_invalid_gemini_format(self):
        self.create_employee()
        self.create_task()
        with patch(
            "backend.main.ai_integration.generate_task_recommendations",
            return_value={"wrong_key": []}
        ):
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 502)
        self.assertIn("invalid recommendation format", response.json()["detail"])

    def test_invalid_gemini_json(self):
        self.create_employee()
        self.create_task()
        with patch(
            "backend.main.ai_integration.generate_task_recommendations",
            side_effect=json.JSONDecodeError("Invalid JSON", "bad", 0)
        ):
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "Gemini returned invalid JSON."
        )

    def test_missing_api_key(self):
        self.create_employee()
        self.create_task()
        with patch(
            "backend.main.ai_integration.generate_task_recommendations",
            side_effect=ValueError(
                "GEMINI_API_KEY is missing from the .env file."
            )
        ):
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["detail"],
            "Gemini API key is not configured."
        )

    def test_gemini_api_failure(self):
        self.create_employee()
        self.create_task()
        with patch(
            "backend.main.ai_integration.generate_task_recommendations",
            side_effect=genai_errors.ServerError(
                503,
                {"error": {"message": "Service unavailable"}}
            )
        ):
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["detail"],
            "Gemini API request failed."
        )

    def test_unknown_task_recommendation_rejected(self):
        employee = self.create_employee()
        self.create_task()
        recommendation = {
            "task_id": 999,
            "employee_id": employee["employee_id"],
            "reason": "Incorrect task ID."
        }
        with self.mock_gemini([recommendation]):
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 502)
        self.assertIn("not eligible", response.json()["detail"])

    def test_missing_database_returns_503(self):
        missing = self.database_path.with_name("missing.db")
        with patch.object(database, "DATABASE_PATH", missing):
            with self.mock_gemini([]) as gemini:
                response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 503)
        gemini.assert_not_called()
        self.assertFalse(missing.exists())

    def test_only_active_task_ids_sent_to_gemini(self):
        self.create_employee()
        active_task = self.create_task(title="Active task")
        completed_task = self.create_task(title="Completed task")
        values = {
            key: value
            for key, value in completed_task.items()
            if key != "task_id"
        }
        response = self.client.put(
            f'/tasks/{completed_task["task_id"]}',
            json={**values, "status": "Completed"}
        )
        self.assertEqual(response.status_code, 200)
        with self.mock_gemini([]) as gemini:
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 200)
        task_information = json.loads(gemini.call_args.args[0])
        self.assertEqual(
            task_information["eligible_task_ids"],
            [active_task["task_id"]]
        )
        self.assertEqual(len(task_information["tasks"]), 2)

    def test_all_inactive_employees_skips_gemini(self):
        employee = self.create_employee()
        self.create_task()
        response = self.client.put(
            f'/employees/{employee["employee_id"]}',
            json={**EMPLOYEE, "status": "Inactive"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        with self.mock_gemini([]) as gemini:
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"recommendations": []})
        gemini.assert_not_called()

    def test_inactive_employees_excluded_from_gemini_data(self):
        active = self.create_employee()
        inactive = self.create_employee(name="Taylor Kim")
        self.create_task()
        response = self.client.put(
            f'/employees/{inactive["employee_id"]}',
            json={**EMPLOYEE, "name": "Taylor Kim", "status": "Inactive"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        with self.mock_gemini([]) as gemini:
            response = self.client.post("/recommendations")
        self.assertEqual(response.status_code, 200, response.text)
        task_information = json.loads(gemini.call_args.args[0])
        self.assertEqual(
            [employee["employee_id"] for employee in task_information["employees"]],
            [active["employee_id"]]
        )


class TestPreviewRecommendationAPI(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="taskflow preview ")
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "taskflow.db"

        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.executescript(
                (PROJECT_ROOT / "backend" / "schema.sql").read_text(
                    encoding="utf-8"
                )
            )
        self.enterContext(
            patch.object(database, "DATABASE_PATH", self.database_path)
        )
        calendar = self.enterContext(patch("backend.main.date"))
        calendar.today.return_value = date(2026, 11, 9)
        self.client = self.enterContext(TestClient(app))

    def create_employee(self, **changes):
        response = self.client.post(
            "/employees",
            json={**EMPLOYEE, **changes}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def create_task(self, **changes):
        response = self.client.post(
            "/tasks",
            json={**TASK, **changes}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def recommend(self, task, employee, reason="Suitable assignment."):
        return {
            "task_id": task["task_id"],
            "employee_id": employee["employee_id"],
            "reason": reason
        }

    def preview(self, recommendation, selected=None):
        return self.client.post(
            "/recommendations/preview",
            json={
                "recommendation": recommendation,
                "selected_recommendations": selected or []
            }
        )

    def test_valid_recommendation_preview(self):
        employee = self.create_employee()
        task = self.create_task()
        response = self.preview(self.recommend(task, employee))
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["valid"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["capacity_errors"], {})
        self.assertEqual(result["fairness_warnings"], [])

    def test_preview_does_not_modify_database(self):
        employee = self.create_employee()
        task = self.create_task()
        response = self.preview(self.recommend(task, employee))
        self.assertEqual(response.status_code, 200, response.text)
        saved_task = self.client.get(
            f'/tasks/{task["task_id"]}'
        ).json()
        self.assertIsNone(saved_task["employee_id"])

    def test_junior_employee_cannot_receive_hard_task(self):
        employee = self.create_employee(experience_level="Junior")
        task = self.create_task(difficulty="Hard")
        response = self.preview(self.recommend(task, employee))
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["valid"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["errors"])

    def test_junior_employee_medium_task_warning(self):
        employee = self.create_employee(experience_level="Junior")
        task = self.create_task(difficulty="Medium")
        response = self.preview(self.recommend(task, employee))
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["valid"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["warnings"])

    def test_mid_employee_hard_task_warning(self):
        employee = self.create_employee(experience_level="Mid")
        task = self.create_task(difficulty="Hard")
        response = self.preview(self.recommend(task, employee))
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["valid"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["warnings"])

    def test_completed_task_cannot_be_previewed(self):
        employee = self.create_employee()
        task = self.create_task()
        values = {
            key: value
            for key, value in task.items()
            if key != "task_id"
        }
        update = self.client.put(
            f'/tasks/{task["task_id"]}',
            json={**values, "status": "Completed"}
        )
        self.assertEqual(update.status_code, 200)
        response = self.preview(self.recommend(task, employee))
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["valid"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["errors"])

    def test_unknown_employee_rejected(self):
        task = self.create_task()
        recommendation = {
            "task_id": task["task_id"],
            "employee_id": 999,
            "reason": "Unknown employee."
        }
        response = self.preview(recommendation)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["valid"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["errors"])

    def test_capacity_conflict_reported(self):
        employee = self.create_employee(available_hours=10)
        task = self.create_task(estimated_hours=20)
        response = self.preview(self.recommend(task, employee))
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["valid"])
        self.assertFalse(result["applied"])
        self.assertIn(str(employee["employee_id"]), result["capacity_errors"])

    def test_selected_recommendations_affect_capacity(self):
        employee = self.create_employee(available_hours=40)
        first_task = self.create_task(
            title="First task",
            estimated_hours=25
        )
        second_task = self.create_task(
            title="Second task",
            estimated_hours=20
        )
        first = self.recommend(first_task, employee)
        second = self.recommend(second_task, employee)
        response = self.preview(second, selected=[first])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["valid"])
        self.assertFalse(result["applied"])
        self.assertIn(str(employee["employee_id"]), result["capacity_errors"])

    def test_existing_capacity_conflict_not_worsened(self):
        employee = self.create_employee(available_hours=10)
        self.create_task(
            title="Existing overload",
            estimated_hours=20,
            employee_id=employee["employee_id"]
        )
        other_employee = self.create_employee(name="Taylor Kim")
        task = self.create_task(
            title="Reassignment",
            estimated_hours=5,
            employee_id=employee["employee_id"]
        )
        response = self.preview(self.recommend(task, other_employee))
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["valid"])
        self.assertFalse(result["applied"])
        self.assertEqual(result["capacity_errors"], {})

    def test_invalid_request_returns_422(self):
        response = self.client.post(
            "/recommendations/preview",
            json={
                "recommendation": {
                    "task_id": -1,
                    "employee_id": 1,
                    "reason": "Invalid task ID."
                },
                "selected_recommendations": []
            }
        )
        self.assertEqual(response.status_code, 422)

    def test_missing_database_returns_503(self):
        missing = self.database_path.with_name("missing.db")
        employee = self.create_employee()
        task = self.create_task()
        recommendation = self.recommend(task, employee)
        with patch.object(database, "DATABASE_PATH", missing):
            response = self.preview(recommendation)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(missing.exists())

    def test_selected_recommendation_is_applied(self):
        employee = self.create_employee()
        task = self.create_task()
        recommendation = self.recommend(task, employee)
        response = self.preview(
            recommendation,
            selected=[recommendation]
        )
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["valid"])
        self.assertTrue(result["applied"])
        self.assertEqual(result["capacity_errors"], {})

    def test_inactive_employee_preview_rejected(self):
        employee = self.create_employee()
        task = self.create_task()
        response = self.client.put(
            f'/employees/{employee["employee_id"]}',
            json={**EMPLOYEE, "status": "Inactive"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        response = self.preview(self.recommend(task, employee))
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["valid"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["errors"])


class TestEvaluateRecommendationsAPI(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="taskflow evaluate ")
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "taskflow.db"
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.executescript(
                (PROJECT_ROOT / "backend" / "schema.sql").read_text(
                    encoding="utf-8"
                )
            )
        self.enterContext(
            patch.object(database, "DATABASE_PATH", self.database_path)
        )
        calendar = self.enterContext(patch("backend.main.date"))
        calendar.today.return_value = date(2026, 11, 9)
        self.client = self.enterContext(TestClient(app))

    def create_employee(self, **changes):
        response = self.client.post(
            "/employees",
            json={**EMPLOYEE, **changes}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def create_task(self, **changes):
        response = self.client.post(
            "/tasks",
            json={**TASK, **changes}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def recommend(self, task, employee, reason="Suitable assignment."):
        return {
            "task_id": task["task_id"],
            "employee_id": employee["employee_id"],
            "reason": reason
        }

    def evaluate(self, recommendations):
        return self.client.post(
            "/recommendations/evaluate",
            json={"selected_recommendations": recommendations}
        )

    def test_valid_selection_can_commit(self):
        employee = self.create_employee()
        task = self.create_task()
        response = self.evaluate([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["can_commit"])
        self.assertTrue(result["recommendations"][0]["valid"])
        self.assertEqual(result["capacity_errors"], {})
        self.assertEqual(result["fairness_warnings"], [])

    def test_empty_selection_cannot_commit(self):
        response = self.evaluate([])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["can_commit"])
        self.assertEqual(result["recommendations"], [])
        self.assertEqual(result["capacity_errors"], {})

    def test_combined_assignments_exceed_capacity(self):
        employee = self.create_employee(available_hours=40)
        first_task = self.create_task(
            title="First task",
            estimated_hours=25
        )
        second_task = self.create_task(
            title="Second task",
            estimated_hours=20
        )
        recommendations = [
            self.recommend(first_task, employee),
            self.recommend(second_task, employee)
        ]
        response = self.evaluate(recommendations)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["can_commit"])
        self.assertTrue(all(
            recommendation["valid"]
            for recommendation in result["recommendations"]
        ))
        self.assertIn(
            str(employee["employee_id"]),
            result["capacity_errors"]
        )

    def test_duplicate_task_rejected(self):
        employee1 = self.create_employee(name="Alex Johnson")
        employee2 = self.create_employee(name="Taylor Kim")
        task = self.create_task()
        recommendations = [
            self.recommend(task, employee1),
            self.recommend(task, employee2)
        ]
        response = self.evaluate(recommendations)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["can_commit"])
        self.assertTrue(all(
            not recommendation["valid"]
            for recommendation in result["recommendations"]
        ))
        self.assertEqual(result["capacity_errors"], {})

    def test_junior_hard_task_blocks_commit(self):
        employee = self.create_employee(experience_level="Junior")
        task = self.create_task(difficulty="Hard")
        response = self.evaluate([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["can_commit"])
        self.assertFalse(result["recommendations"][0]["valid"])
        self.assertTrue(result["recommendations"][0]["errors"])

    def test_experience_warning_does_not_block_commit(self):
        employee = self.create_employee(experience_level="Junior")
        task = self.create_task(difficulty="Medium")
        response = self.evaluate([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["can_commit"])
        self.assertTrue(result["recommendations"][0]["valid"])
        self.assertTrue(result["recommendations"][0]["warnings"])

    def test_completed_task_blocks_commit(self):
        employee = self.create_employee()
        task = self.create_task()
        values = {
            key: value
            for key, value in task.items()
            if key != "task_id"
        }
        update = self.client.put(
            f'/tasks/{task["task_id"]}',
            json={**values, "status": "Completed"}
        )
        self.assertEqual(update.status_code, 200)
        response = self.evaluate([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["can_commit"])
        self.assertFalse(result["recommendations"][0]["valid"])

    def test_existing_conflict_not_worsened(self):
        employee = self.create_employee(available_hours=10)
        self.create_task(
            title="Existing overload",
            estimated_hours=20,
            employee_id=employee["employee_id"]
        )
        other_employee = self.create_employee(name="Taylor Kim")
        task = self.create_task(
            title="Task to reassign",
            estimated_hours=5,
            employee_id=employee["employee_id"]
        )
        response = self.evaluate([
            self.recommend(task, other_employee)
        ])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["can_commit"])
        self.assertEqual(result["capacity_errors"], {})

    def test_fairness_warning_does_not_block_commit(self):
        employee1 = self.create_employee(name="Alex Johnson")
        self.create_employee(name="Taylor Kim")
        task = self.create_task(
            priority="High",
            difficulty="Hard"
        )
        response = self.evaluate([
            self.recommend(task, employee1)
        ])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertTrue(result["can_commit"])
        self.assertTrue(result["fairness_warnings"])

    def test_evaluate_does_not_modify_database(self):
        employee = self.create_employee()
        task = self.create_task()
        response = self.evaluate([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 200, response.text)
        saved_task = self.client.get(
            f'/tasks/{task["task_id"]}'
        ).json()
        self.assertIsNone(saved_task["employee_id"])

    def test_invalid_request_returns_422(self):
        response = self.client.post(
            "/recommendations/evaluate",
            json={
                "selected_recommendations": [
                    {
                        "task_id": -1,
                        "employee_id": 1,
                        "reason": "Invalid ID."
                    }
                ]
            }
        )
        self.assertEqual(response.status_code, 422)

    def test_missing_database_returns_503(self):
        employee = self.create_employee()
        task = self.create_task()
        missing = self.database_path.with_name("missing.db")
        with patch.object(database, "DATABASE_PATH", missing):
            response = self.evaluate([
                self.recommend(task, employee)
            ])
        self.assertEqual(response.status_code, 503)
        self.assertFalse(missing.exists())

    def test_inactive_employee_blocks_commit(self):
        employee = self.create_employee()
        task = self.create_task()
        response = self.client.put(
            f'/employees/{employee["employee_id"]}',
            json={**EMPLOYEE, "status": "Inactive"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        response = self.evaluate([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertFalse(result["can_commit"])
        self.assertFalse(result["recommendations"][0]["valid"])


class TestApproveRecommendationsAPI(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="taskflow approve ")
        self.addCleanup(temporary.cleanup)
        self.database_path = Path(temporary.name) / "taskflow.db"
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.executescript(
                (PROJECT_ROOT / "backend" / "schema.sql").read_text(
                    encoding="utf-8"
                )
            )
        self.enterContext(
            patch.object(database, "DATABASE_PATH", self.database_path)
        )
        calendar = self.enterContext(patch("backend.main.date"))
        calendar.today.return_value = date(2026, 11, 9)
        self.client = self.enterContext(TestClient(app))

    def create_employee(self, **changes):
        response = self.client.post(
            "/employees",
            json={**EMPLOYEE, **changes}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def create_task(self, **changes):
        response = self.client.post(
            "/tasks",
            json={**TASK, **changes}
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def recommend(self, task, employee, reason="Suitable assignment."):
        return {
            "task_id": task["task_id"],
            "employee_id": employee["employee_id"],
            "reason": reason
        }

    def approve(self, recommendations):
        return self.client.post(
            "/recommendations/approve",
            json={"selected_recommendations": recommendations}
        )

    def saved_task(self, task):
        response = self.client.get(f'/tasks/{task["task_id"]}')
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_approve_one_assignment(self):
        employee = self.create_employee()
        task = self.create_task()
        response = self.approve([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["updated_task_ids"],
            [task["task_id"]]
        )
        self.assertEqual(
            self.saved_task(task)["employee_id"],
            employee["employee_id"]
        )

    def test_approve_multiple_assignments(self):
        employee1 = self.create_employee(name="Alex Johnson")
        employee2 = self.create_employee(name="Taylor Kim")
        task1 = self.create_task(title="First task", estimated_hours=10)
        task2 = self.create_task(title="Second task", estimated_hours=10)
        response = self.approve([self.recommend(task1, employee1), self.recommend(task2, employee2)])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["updated_task_ids"], [task1["task_id"], task2["task_id"]])
        self.assertEqual(self.saved_task(task1)["employee_id"], employee1["employee_id"])
        self.assertEqual(self.saved_task(task2)["employee_id"], employee2["employee_id"])

    def test_empty_selection_rejected(self):
        response = self.approve([])
        self.assertEqual(response.status_code, 400)
        self.assertIn("No recommendations selected", response.json()["detail"])

    def test_junior_hard_task_rejected(self):
        employee = self.create_employee(experience_level="Junior")
        task = self.create_task(difficulty="Hard")
        response = self.approve([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.saved_task(task)["employee_id"])

    def test_experience_warning_allows_approval(self):
        employee = self.create_employee(experience_level="Junior")
        task = self.create_task(difficulty="Medium")
        response = self.approve([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.saved_task(task)["employee_id"], employee["employee_id"])

    def test_combined_capacity_conflict_rejected(self):
        employee = self.create_employee(available_hours=40)
        task1 = self.create_task(title="First task", estimated_hours=25)
        task2 = self.create_task(title="Second task", estimated_hours=20)
        response = self.approve([self.recommend(task1, employee),self.recommend(task2, employee)])
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.saved_task(task1)["employee_id"])
        self.assertIsNone(self.saved_task(task2)["employee_id"])

    def test_duplicate_task_rejected(self):
        employee1 = self.create_employee(name="Alex Johnson")
        employee2 = self.create_employee(name="Taylor Kim")
        task = self.create_task()
        response = self.approve([self.recommend(task, employee1), self.recommend(task, employee2)])
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.saved_task(task)["employee_id"])

    def test_completed_task_rejected(self):
        employee = self.create_employee()
        task = self.create_task()
        with database.get_connection() as connection:
            connection.execute(
                "UPDATE tasks SET status = 'Completed' WHERE task_id = ?",
                (task["task_id"],)
            )
        response = self.approve([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.saved_task(task)["employee_id"])

    def test_invalid_request_returns_422(self):
        response = self.client.post(
            "/recommendations/approve",
            json={
                "selected_recommendations": [
                    {
                        "task_id": -1,
                        "employee_id": 1,
                        "reason": "Invalid ID."
                    }
                ]
            }
        )
        self.assertEqual(response.status_code, 422)

    def test_missing_database_returns_503(self):
        employee = self.create_employee()
        task = self.create_task()
        missing = self.database_path.with_name("missing.db")
        with patch.object(database, "DATABASE_PATH", missing):
            response = self.approve([
                self.recommend(task, employee)
            ])
        self.assertEqual(response.status_code, 503)
        self.assertFalse(missing.exists())

    def test_database_update_conflict_returns_409(self):
        employee = self.create_employee()
        task = self.create_task()
        with patch(
            "backend.database.approve_assignments",
            side_effect=ValueError("Task is no longer eligible.")
        ):
            response = self.approve([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 409)
        self.assertIn("no longer eligible", response.json()["detail"])
        self.assertIsNone(self.saved_task(task)["employee_id"])

    def test_transaction_rolls_back_on_failure(self):
        employee = self.create_employee()
        task1 = self.create_task(title="First task", estimated_hours=5)
        task2 = self.create_task(title="Second task", estimated_hours=5)
        recommendations = [self.recommend(task1, employee), self.recommend(task2, employee)]
        with database.get_connection() as connection:
            connection.execute(
                "UPDATE tasks SET status = 'Completed' WHERE task_id = ?",
                (task2["task_id"],)
            )
        with self.assertRaises(ValueError):
            database.approve_assignments(recommendations)
        self.assertIsNone(self.saved_task(task1)["employee_id"])
        self.assertIsNone(self.saved_task(task2)["employee_id"])

    def test_approval_preserves_other_task_fields(self):
        employee = self.create_employee()
        task = self.create_task(
            title="Important report",
            estimated_hours=12,
            priority="High",
            difficulty="Easy"
        )
        response = self.approve([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.saved_task(task)
        self.assertEqual(saved["title"], task["title"])
        self.assertEqual(saved["estimated_hours"], task["estimated_hours"])
        self.assertEqual(saved["deadline"], task["deadline"])
        self.assertEqual(saved["priority"], task["priority"])
        self.assertEqual(saved["difficulty"], task["difficulty"])
        self.assertEqual(saved["status"], task["status"])
        self.assertEqual(saved["employee_id"], employee["employee_id"])

    def test_approval_revalidates_current_capacity(self):
        employee = self.create_employee(available_hours=40)
        task = self.create_task(estimated_hours=15)
        recommendation = self.recommend(task, employee)
        evaluation = self.client.post(
            "/recommendations/evaluate",
            json={"selected_recommendations": [recommendation]}
        )
        self.assertEqual(evaluation.status_code, 200)
        self.assertTrue(evaluation.json()["can_commit"])
        with database.get_connection() as connection:
            connection.execute(
                "UPDATE employees SET available_hours = 5 WHERE employee_id = ?",
                (employee["employee_id"],)
            )
        response = self.approve([recommendation])
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.saved_task(task)["employee_id"])

    def test_inactive_employee_approval_rejected(self):
        employee = self.create_employee()
        task = self.create_task()
        response = self.client.put(
            f'/employees/{employee["employee_id"]}',
            json={**EMPLOYEE, "status": "Inactive"}
        )
        self.assertEqual(response.status_code, 200, response.text)
        response = self.approve([self.recommend(task, employee)])
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(self.saved_task(task)["employee_id"])


if __name__ == "__main__":
    unittest.main()
