import json
import unittest
from unittest.mock import patch

from backend.ai_integration import format_task_information

class TestFormatTaskInformation(unittest.TestCase):
    def setUp(self):
        self.employees = [
            {"employee_id": 1, "name": "Sarah", "status": "Active"},
            {"employee_id": 2, "name": "James", "status": "Inactive"},
            {"employee_id": 3, "name": "Alex", "status": "Active"}
        ]
        self.tasks = [
            {"task_id": 101, "status": "Active", "employee_id": None},
            {"task_id": 102, "status": "Completed", "employee_id": 2}
        ]
        self.workload_summary = {"total_employees": 2}
        self.eligible_task_ids = [101]

    @patch("backend.ai_integration.date")
    def test_inactive_employees_excluded(self, mock_date):
        mock_date.today.return_value.isoformat.return_value = "2026-11-09"
        result = format_task_information(
            self.employees,
            self.tasks,
            self.workload_summary,
            self.eligible_task_ids
        )
        data = json.loads(result)
        self.assertEqual(
            [employee["employee_id"] for employee in data["employees"]],
            [1, 3]
        )
        self.assertEqual(len(data["tasks"]), 2)
        self.assertEqual(data["eligible_task_ids"], [101])
        self.assertEqual(data["employee_workloads"], [])
        self.assertEqual(data["fairness"], {})
        self.assertEqual(data["today"], "2026-11-09")

    def test_all_employees_inactive(self):
        for employee in self.employees:
            employee["status"] = "Inactive"
        result = format_task_information(
            self.employees,
            self.tasks,
            self.workload_summary,
            self.eligible_task_ids
        )
        data = json.loads(result)
        self.assertEqual(data["employees"], [])

    def test_original_employees_not_modified(self):
        original = [employee.copy() for employee in self.employees]
        format_task_information(
            self.employees,
            self.tasks,
            self.workload_summary,
            self.eligible_task_ids
        )
        self.assertEqual(self.employees, original)


if __name__ == "__main__":
    unittest.main()