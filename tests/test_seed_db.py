"""Automated tests for sample database seeding."""

import unittest
from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import runpy

from backend import init_db, database, seed_db


class TestDatabaseSeeding(unittest.TestCase):

    def setUp(self):
        """Create an empty temporary database for each test."""
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.db_path = (
            Path(self.temp_dir.name) / "test.db"
        )

        patches = [
            patch.object(
                init_db, "database_path", self.db_path
            ),
            patch.object(
                database, "DATABASE_PATH", self.db_path
            ),
        ]

        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        init_db.initialize_database()

    def test_seeds_sample_employees(self):
        """Seeding creates the expected sample employees."""
        seed_db.seed_database()

        employees = database.get_employees()

        self.assertEqual(len(employees), 3)

        self.assertEqual(
            {employee["name"] for employee in employees},
            {"Sarah", "James", "Alex"},
        )

    def test_seeds_sample_tasks(self):
        """Seeding creates six sample tasks."""
        seed_db.seed_database()

        self.assertEqual(len(database.get_tasks()), 6)

    def test_sample_task_assignments(self):
        """Sample tasks include valid assignments and an unassigned task."""
        seed_db.seed_database()

        employee_ids = {
            employee["employee_id"]
            for employee in database.get_employees()
        }

        tasks = database.get_tasks()

        assigned = [
            task for task in tasks
            if task["employee_id"] is not None
        ]

        unassigned = [
            task for task in tasks
            if task["employee_id"] is None
        ]

        self.assertEqual(len(assigned), 5)
        self.assertEqual(len(unassigned), 1)

        for task in assigned:
            self.assertIn(
                task["employee_id"], employee_ids
            )

    def test_relative_deadlines(self):
        """Sample deadlines are relative to the seeding date."""
        fixed_today = date(2026, 11, 27)

        with patch("backend.seed_db.date") as mock_date:
            mock_date.today.return_value = fixed_today

            seed_db.seed_database()

        expected_offsets = {
            "Prepare project report": 3,
            "Review documentation": 3,
            "Update database": -3,
            "Test application": 1,
            "Organize project files": 7,
            "Design new feature": 14,
        }

        for task in database.get_tasks():
            expected_deadline = (
                fixed_today
                + timedelta(days=expected_offsets[task["title"]])
            ).isoformat()

            self.assertEqual(
                task["deadline"],
                expected_deadline,
            )

    def test_repeated_seeding_does_not_duplicate_data(self):
        """Repeated seeding preserves the original sample records."""
        seed_db.seed_database()

        employees_before = database.get_employees()
        tasks_before = database.get_tasks()

        seed_db.seed_database()

        self.assertEqual(
            database.get_employees(),
            employees_before,
        )
        self.assertEqual(
            database.get_tasks(),
            tasks_before,
        )

    def test_skips_database_with_existing_employees(self):
        """Seeding does not modify existing employee data."""
        database.add_employee(
            "Existing Employee", 40, "Senior"
        )

        employees_before = database.get_employees()

        seed_db.seed_database()

        self.assertEqual(
            database.get_employees(),
            employees_before,
        )
        self.assertEqual(database.get_tasks(), [])

    def test_skips_database_with_existing_tasks(self):
        """Seeding does not modify existing task data."""
        database.add_task(
            "Existing Task",
            5,
            "2030-01-01",
            "Medium",
            "Easy",
        )

        tasks_before = database.get_tasks()

        seed_db.seed_database()

        self.assertEqual(database.get_employees(), [])
        self.assertEqual(
            database.get_tasks(),
            tasks_before,
        )

    def test_script_entry_point(self):
        """Direct script execution seeds the database."""
        runpy.run_path(
            str(Path(seed_db.__file__).resolve()),
            run_name="__main__",
        )

        self.assertEqual(len(database.get_employees()), 3)
        self.assertEqual(len(database.get_tasks()), 6)

    def test_employee_retrieval_failure(self):
        """Failed employee retrieval prevents sample insertion."""
        with patch(
            "backend.seed_db.get_employees",
            side_effect=RuntimeError("Database unavailable."),
        ):
            with self.assertRaises(RuntimeError):
                seed_db.seed_database()

        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_task_retrieval_failure(self):
        """Failed task retrieval prevents sample insertion."""
        with patch(
            "backend.seed_db.get_tasks",
            side_effect=RuntimeError("Database unavailable."),
        ):
            with self.assertRaises(RuntimeError):
                seed_db.seed_database()

        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_employee_insertion_failure(self):
        """Failed employee insertion prevents task creation."""
        with patch(
            "backend.seed_db.add_employee",
            side_effect=RuntimeError("Employee insertion failed."),
        ):
            with patch(
                "backend.seed_db.add_task"
            ) as mock_add_task:
                with self.assertRaises(RuntimeError):
                    seed_db.seed_database()

                mock_add_task.assert_not_called()

        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_expected_employee_assignments(self):
        """Sample tasks are assigned to the intended employees."""
        seed_db.seed_database()

        employees = {
            employee["employee_id"]: employee["name"]
            for employee in database.get_employees()
        }

        expected_assignments = {
            "Prepare project report": "Sarah",
            "Review documentation": "Sarah",
            "Update database": "James",
            "Test application": "James",
            "Organize project files": "Alex",
            "Design new feature": None,
        }

        actual_assignments = {
            task["title"]: employees.get(task["employee_id"])
            for task in database.get_tasks()
        }

        self.assertEqual(
            actual_assignments,
            expected_assignments,
        )


if __name__ == "__main__":
    unittest.main()