"""Comprehensive tests for TaskFlow AI's SQLite database operations.

Run from the repository root:
    python -m unittest discover -s tests -v
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing

from backend import database


class TestDatabase(unittest.TestCase):
    """Each test uses an independent temporary database with the real schema."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "test.db"
        schema_path = Path(__file__).resolve().parent.parent / "backend" / "schema.sql"

        with closing(sqlite3.connect(self.db_path)) as connection:
            connection.executescript(schema_path.read_text(encoding="utf-8"))

        db_patch = patch.object(database, "DATABASE_PATH", self.db_path)
        db_patch.start()
        self.addCleanup(db_patch.stop)

    def add_sample_employee(self, name="Sarah", hours=40, level="Mid"):
        return database.add_employee(name, hours, level)

    def add_sample_task(
        self, title="Prepare report", hours=10, deadline="2026-11-12",
        priority="High", difficulty="Medium", employee_id=None,
    ):
        return database.add_task(
            title, hours, deadline, priority, difficulty, employee_id
        )

    # EMPLOYEE READ OPERATIONS

    def test_get_employees_empty(self):
        self.assertEqual(database.get_employees(), [])

    def test_get_employees_multiple_and_all_fields(self):
        expected = {
            self.add_sample_employee("Sarah", 40, "Mid"):
                ("Sarah", 40, "Mid"),
            self.add_sample_employee("James", 30, "Junior"):
                ("James", 30, "Junior"),
            self.add_sample_employee("Alex", 20.5, "Senior"):
                ("Alex", 20.5, "Senior"),
        }
        employees = database.get_employees()
        self.assertEqual(len(employees), 3)
        self.assertTrue(all(isinstance(e, dict) for e in employees))
        self.assertEqual({e["employee_id"] for e in employees}, set(expected))
        for employee in employees:
            name, hours, level = expected[employee["employee_id"]]
            self.assertEqual(employee["name"], name)
            self.assertEqual(employee["available_hours"], hours)
            self.assertEqual(employee["experience_level"], level)

    def test_get_employee_existing(self):
        employee_id = self.add_sample_employee()
        self.assertEqual(database.get_employee(employee_id), {
            "employee_id": employee_id,
            "name": "Sarah",
            "available_hours": 40,
            "experience_level": "Mid",
        })

    def test_get_employee_missing(self):
        self.assertIsNone(database.get_employee(999))
        self.assertIsNone(database.get_employee(-1))

    # EMPLOYEE CREATE AND UPDATE

    def test_add_employee_returns_unique_integer_ids(self):
        first = self.add_sample_employee()
        second = self.add_sample_employee("James", 30, "Junior")
        self.assertIsInstance(first, int)
        self.assertIsInstance(second, int)
        self.assertNotEqual(first, second)
        self.assertEqual(len(database.get_employees()), 2)

    def test_add_employee_accepts_zero_and_fractional_hours(self):
        zero_id = self.add_sample_employee("Zero", 0, "Junior")
        part_id = self.add_sample_employee("Part-time", 17.5, "Senior")
        self.assertEqual(database.get_employee(zero_id)["available_hours"], 0)
        self.assertEqual(database.get_employee(part_id)["available_hours"], 17.5)

    def test_add_employee_accepts_all_experience_levels(self):
        for level in ("Junior", "Mid", "Senior"):
            with self.subTest(level=level):
                employee_id = self.add_sample_employee(level=level)
                self.assertEqual(database.get_employee(employee_id)["experience_level"], level)

    def test_update_employee_changes_all_editable_fields(self):
        employee_id = self.add_sample_employee()
        self.assertTrue(database.update_employee(employee_id, "Sarah Updated", 22.5, "Senior"))
        self.assertEqual(database.get_employee(employee_id), {
            "employee_id": employee_id,
            "name": "Sarah Updated",
            "available_hours": 22.5,
            "experience_level": "Senior",
        })

    def test_update_employee_missing_returns_false(self):
        self.assertFalse(database.update_employee(999, "Nobody", 20, "Junior"))
        self.assertEqual(database.get_employees(), [])

    def test_update_employee_same_values_still_reports_match(self):
        employee_id = self.add_sample_employee()
        self.assertTrue(database.update_employee(employee_id, "Sarah", 40, "Mid"))
  
    def test_update_employee_rejects_invalid_values(self):
        employee_id = self.add_sample_employee()
        original = database.get_employee(employee_id)

        invalid_cases = (
            ("", 40, "Mid"),
            ("   ", 40, "Mid"),
            (None, 40, "Mid"),
            ("Sarah", -1, "Mid"),
            ("Sarah", None, "Mid"),
            ("Sarah", 40, "Expert"),
            ("Sarah", 40, None),
        )

        for name, hours, level in invalid_cases:
            with self.subTest(name=name, hours=hours, level=level):
                with self.assertRaises(sqlite3.IntegrityError):
                    database.update_employee(employee_id, name, hours, level)
                self.assertEqual(database.get_employee(employee_id),original)

    # TASK READ OPERATIONS

    def test_get_tasks_empty(self):
        self.assertEqual(database.get_tasks(), [])

    def test_get_tasks_multiple_including_unassigned(self):
        employee_id = self.add_sample_employee()
        ids = {
            self.add_sample_task("A", 3, employee_id=employee_id),
            self.add_sample_task("B", 5),
            self.add_sample_task("C", 8, priority="Low", difficulty="Easy"),
        }
        tasks = database.get_tasks()
        self.assertEqual(len(tasks), 3)
        self.assertTrue(all(isinstance(task, dict) for task in tasks))
        self.assertEqual({task["task_id"] for task in tasks}, ids)
        self.assertEqual({task["title"] for task in tasks}, {"A", "B", "C"})

        tasks_by_title = {task["title"]: task for task in tasks}

        self.assertEqual(tasks_by_title["A"]["employee_id"], employee_id)
        self.assertIsNone(tasks_by_title["B"]["employee_id"])
        self.assertIsNone(tasks_by_title["C"]["employee_id"])

    def test_get_task_existing_checks_every_field_and_default_status(self):
        employee_id = self.add_sample_employee()
        task_id = self.add_sample_task(employee_id=employee_id)
        self.assertEqual(database.get_task(task_id), {
            "task_id": task_id,
            "title": "Prepare report",
            "estimated_hours": 10,
            "deadline": "2026-11-12",
            "priority": "High",
            "difficulty": "Medium",
            "status": "Active",
            "employee_id": employee_id,
        })

    def test_get_task_missing(self):
        self.assertIsNone(database.get_task(999))
        self.assertIsNone(database.get_task(-1))

    def test_get_tasks_by_employee_filters_correctly(self):
        sarah_id = self.add_sample_employee()
        james_id = self.add_sample_employee("James", 30, "Junior")
        sarah_first = self.add_sample_task("Sarah A", 5, employee_id=sarah_id)
        sarah_second = self.add_sample_task("Sarah B", 10, employee_id=sarah_id)
        self.add_sample_task("James task", 8, employee_id=james_id)
        self.add_sample_task("Unassigned", 4)

        tasks = database.get_tasks_by_employee(sarah_id)
        self.assertEqual({task["task_id"] for task in tasks}, {sarah_first, sarah_second})
        self.assertEqual(len(database.get_tasks()), 4)
        self.assertEqual(len(database.get_tasks_by_employee(james_id)), 1)
        self.assertEqual(database.get_tasks_by_employee(999), [])

    def test_get_tasks_by_employee_includes_completed_tasks(self):
        employee_id = self.add_sample_employee()
        active_id = self.add_sample_task("Active", 5, employee_id=employee_id)
        done_id = self.add_sample_task("Done", 3, employee_id=employee_id)
        self.assertTrue(database.update_task(
            done_id, "Done", 3, "2026-11-12", "High", "Medium",
            "Completed", employee_id,
        ))
        tasks = database.get_tasks_by_employee(employee_id)
        self.assertEqual({t["task_id"] for t in tasks}, {active_id, done_id})
        self.assertEqual({t["status"] for t in tasks}, {"Active", "Completed"})

    # TASK CREATE AND UPDATE

    def test_add_task_returns_unique_integer_ids(self):
        first = self.add_sample_task("First")
        second = self.add_sample_task("Second")
        self.assertIsInstance(first, int)
        self.assertIsInstance(second, int)
        self.assertNotEqual(first, second)

    def test_add_task_defaults_to_unassigned_and_active(self):
        task_id = self.add_sample_task()
        task = database.get_task(task_id)
        self.assertIsNone(task["employee_id"])
        self.assertEqual(task["status"], "Active")

    def test_add_task_accepts_fractional_hours_and_valid_enums(self):
        for priority in ("Low", "Medium", "High"):
            for difficulty in ("Easy", "Medium", "Hard"):
                with self.subTest(priority=priority, difficulty=difficulty):
                    task_id = self.add_sample_task(
                        f"{priority}-{difficulty}", 0.5,
                        priority=priority, difficulty=difficulty,
                    )
                    task = database.get_task(task_id)
                    self.assertEqual(task["estimated_hours"], 0.5)
                    self.assertEqual(task["priority"], priority)
                    self.assertEqual(task["difficulty"], difficulty)

    
    def test_task_valid_calendar_dates(self):
        for deadline in (
            "2026-11-12",
            "2028-02-29",
            "2026-12-31",
        ):
            with self.subTest(deadline=deadline):
                task_id = self.add_sample_task(deadline=deadline)
                self.assertEqual(
                    database.get_task(task_id)["deadline"],
                    deadline
                )


    def test_task_invalid_calendar_dates_rejected(self):
        invalid_dates = (
            "2026-02-30",
            "2026-13-01",
            "2026-00-10",
            "2026-11-31",
            "2026-99-99",
            "2025-02-29",
            "11/12/2026",
            "2026-1-12",
            "",
            None,
        )

        for deadline in invalid_dates:
            with self.subTest(deadline=deadline):
                with self.assertRaises(ValueError):
                    self.add_sample_task(deadline=deadline)

        self.assertEqual(database.get_tasks(), [])


    def test_update_task_changes_every_editable_field(self):
        employee_id = self.add_sample_employee()
        task_id = self.add_sample_task()
        self.assertTrue(database.update_task(
            task_id, "Updated title", 6.5, "2026-12-01", "Low",
            "Hard", "Completed", employee_id,
        ))
        self.assertEqual(database.get_task(task_id), {
            "task_id": task_id,
            "title": "Updated title",
            "estimated_hours": 6.5,
            "deadline": "2026-12-01",
            "priority": "Low",
            "difficulty": "Hard",
            "status": "Completed",
            "employee_id": employee_id,
        })

    def test_update_task_can_reassign_and_unassign(self):
        first_employee = self.add_sample_employee()
        second_employee = self.add_sample_employee("James", 30, "Junior")
        task_id = self.add_sample_task(employee_id=first_employee)
        self.assertTrue(database.update_task(
            task_id, "Prepare report", 10, "2026-11-12", "High",
            "Medium", "Active", second_employee,
        ))
        self.assertEqual(database.get_tasks_by_employee(first_employee), [])
        self.assertEqual(len(database.get_tasks_by_employee(second_employee)), 1)
        self.assertTrue(database.update_task(
            task_id, "Prepare report", 10, "2026-11-12", "High",
            "Medium", "Active", None,
        ))
        self.assertIsNone(database.get_task(task_id)["employee_id"])
        self.assertEqual(database.get_tasks_by_employee(second_employee), [])

    def test_update_task_can_reopen_completed_task(self):
        task_id = self.add_sample_task()
        self.assertTrue(database.update_task(
            task_id, "Prepare report", 10, "2026-11-12", "High",
            "Medium", "Completed", None,
        ))
        self.assertTrue(database.update_task(
            task_id, "Prepare report", 10, "2026-11-12", "High",
            "Medium", "Active", None,
        ))
        self.assertEqual(database.get_task(task_id)["status"], "Active")

    def test_update_task_missing_returns_false(self):
        self.assertFalse(database.update_task(
            999, "Missing", 5, "2026-11-12", "Low", "Easy", "Active", None,
        ))
        self.assertEqual(database.get_tasks(), [])

    def test_update_task_same_values_still_reports_match(self):
        task_id = self.add_sample_task()
        self.assertTrue(database.update_task(
            task_id, "Prepare report", 10, "2026-11-12", "High",
            "Medium", "Active", None,
        ))

    
    def test_update_task_rejects_invalid_values(self):
        task_id = self.add_sample_task()
        original = database.get_task(task_id)

        invalid_cases = (
            ("", 5, "2026-11-12", "High", "Easy", "Active", None),
            ("   ", 5, "2026-11-12", "High", "Easy", "Active", None),
            (None, 5, "2026-11-12", "High", "Easy", "Active", None),
            ("Task", 0, "2026-11-12", "High", "Easy", "Active", None),
            ("Task", -5, "2026-11-12", "High", "Easy", "Active", None),
            ("Task", None, "2026-11-12", "High", "Easy", "Active", None),
            ("Task", 5, "2026-11-12", "Urgent", "Easy", "Active", None),
            ("Task", 5, "2026-11-12", None, "Easy", "Active", None),
            ("Task", 5, "2026-11-12", "High", "Extreme", "Active", None),
            ("Task", 5, "2026-11-12", "High", None, "Active", None),
            ("Task", 5, "2026-11-12", "High", "Easy", "In Progress", None),
            ("Task", 5, "2026-11-12", "High", "Easy", None, None),
            ("Task", 5, "2026-11-12", "High", "Easy", "Active", 999),
        )

        for title, hours, deadline, priority, difficulty, status, employee_id in invalid_cases:
            with self.subTest(
                title=title,
                hours=hours,
                priority=priority,
                difficulty=difficulty,
                status=status,
                employee_id=employee_id
            ):
                with self.assertRaises(sqlite3.IntegrityError):
                    database.update_task(
                        task_id, title, hours, deadline,
                        priority, difficulty, status, employee_id
                    )

                self.assertEqual(database.get_task(task_id), original)

    
    def test_update_task_rejects_invalid_dates(self):
        task_id = self.add_sample_task()
        original = database.get_task(task_id)

        for deadline in ("2026-02-30", "2026-99-99", None):
            with self.subTest(deadline=deadline):
                with self.assertRaises(ValueError):
                    database.update_task(
                        task_id, "Changed", 5, deadline,
                        "High", "Easy", "Active", None
                    )
                self.assertEqual(database.get_task(task_id), original)

    # CONSTRAINTS AND ERROR HANDLING

    def test_employee_invalid_values_rejected(self):
        invalid_cases = (
            ("", 40, "Expert"),
            ("Sarah", -1, "Junior"),
            ("Sarah", 40, "junior"),
            ("Sarah", 40, None),
            (None, 40, "Mid"),
            ("Sarah", None, "Mid"),
        )
        for name, hours, level in invalid_cases:
            with self.subTest(name=name, hours=hours, level=level):
                with self.assertRaises(sqlite3.IntegrityError):
                    database.add_employee(name, hours, level)
        self.assertEqual(database.get_employees(), [])

    def test_employee_empty_and_whitespace_names_rejected(self):
        for name in ("", " ", "   "):
            with self.subTest(name=repr(name)):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.add_sample_employee(name=name)

        self.assertEqual(database.get_employees(), [])

    def test_task_invalid_values_rejected(self):
        invalid_cases = (
            ("Task", 0, "2026-11-12", "High", "Easy", None),
            ("Task", -2, "2026-11-12", "High", "Easy", None),
            ("Task", None, "2026-11-12", "High", "Easy", None),
            (None, 5, "2026-11-12", "High", "Easy", None),
            ("Task", 5, "2026-11-12", "Urgent", "Easy", None),
            ("Task", 5, "2026-11-12", None, "Easy", None),
            ("Task", 5, "2026-11-12", "High", "Extreme", None),
            ("Task", 5, "2026-11-12", "High", None, None),
            ("Task", 5, "2026-11-12", "High", "Easy", 999),
        )
        for title, hours, deadline, priority, difficulty, employee_id in invalid_cases:
            with self.subTest(title=title, hours=hours, deadline=deadline,
                              priority=priority, difficulty=difficulty,
                              employee_id=employee_id):
                with self.assertRaises(sqlite3.IntegrityError):
                    database.add_task(
                        title, hours, deadline, priority, difficulty, employee_id
                    )
        self.assertEqual(database.get_tasks(), [])

    def test_task_empty_and_whitespace_titles_rejected(self):
        for title in ("", " ", "   "):
            with self.subTest(title=repr(title)):
                with self.assertRaises(sqlite3.IntegrityError):
                    self.add_sample_task(title=title)

        self.assertEqual(database.get_tasks(), [])


    def test_update_employee_constraint_failure_preserves_old_values(self):
        employee_id = self.add_sample_employee()
        original = database.get_employee(employee_id)
        with self.assertRaises(sqlite3.IntegrityError):
            database.update_employee(employee_id, "Changed", -5, "Senior")
        self.assertEqual(database.get_employee(employee_id), original)

    def test_update_task_invalid_status_preserves_old_values(self):
        task_id = self.add_sample_task()
        original = database.get_task(task_id)
        with self.assertRaises(sqlite3.IntegrityError):
            database.update_task(
                task_id, "Changed", 5, "2026-11-12", "Low",
                "Easy", "In Progress", None,
            )
        self.assertEqual(database.get_task(task_id), original)

    def test_update_task_invalid_foreign_key_preserves_old_values(self):
        task_id = self.add_sample_task()
        original = database.get_task(task_id)
        with self.assertRaises(sqlite3.IntegrityError):
            database.update_task(
                task_id, "Changed", 5, "2026-11-12", "Low",
                "Easy", "Active", 999,
            )
        self.assertEqual(database.get_task(task_id), original)

    
    def test_failed_update_preserves_other_records(self):
        first_id = self.add_sample_employee("Sarah", 40, "Mid")
        second_id = self.add_sample_employee("James", 30, "Junior")

        first_original = database.get_employee(first_id)
        second_original = database.get_employee(second_id)

        with self.assertRaises(sqlite3.IntegrityError):
            database.update_employee(first_id, "Changed", -10, "Senior")

        self.assertEqual(database.get_employee(first_id), first_original)
        self.assertEqual(database.get_employee(second_id), second_original)
        self.assertEqual(len(database.get_employees()), 2)


    def test_sql_injection_text_is_stored_as_data(self):
        suspicious = "Robert'); DROP TABLE employees; --"
        employee_id = self.add_sample_employee(suspicious)
        self.assertEqual(database.get_employee(employee_id)["name"], suspicious)
        task_id = self.add_sample_task(suspicious)
        self.assertEqual(database.get_task(task_id)["title"], suspicious)
        self.assertEqual(len(database.get_employees()), 1)
        self.assertEqual(len(database.get_tasks()), 1)

    def test_connections_are_closed_after_success_and_error(self):
        # Our connection helper should release its connection after each operation.
        with database.get_connection() as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

        with self.assertRaises(RuntimeError):
            with database.get_connection() as failed_connection:
                raise RuntimeError("Simulated failure")
        with self.assertRaises(sqlite3.ProgrammingError):
            failed_connection.execute("SELECT 1")

    def test_failed_transaction_rolls_back_and_connection_closes(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with database.get_connection() as connection:
                connection.execute(
                    "INSERT INTO employees (name, available_hours, experience_level) "
                    "VALUES (?, ?, ?)", ("Valid", 40, "Mid"),
                )
                connection.execute(
                    "INSERT INTO employees (name, available_hours, experience_level) "
                    "VALUES (?, ?, ?)", ("Invalid", -5, "Mid"),
                )
        self.assertEqual(database.get_employees(), [])
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
