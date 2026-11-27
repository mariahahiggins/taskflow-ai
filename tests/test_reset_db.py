"""Automated tests for safe database resetting."""

import runpy
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import closing
import os
import stat

from backend import init_db, database, reset_db


class TestDatabaseReset(unittest.TestCase):

    def setUp(self):
        """Create an isolated database for each test."""
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.db_path = Path(self.temp_dir.name) / "test.db"

        patches = [
            patch.object(
                init_db, "database_path", self.db_path
            ),
            patch.object(
                database, "DATABASE_PATH", self.db_path
            ),
            patch.object(
                reset_db, "database_path", self.db_path
            ),
        ]

        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        init_db.initialize_database()

        employee_id = database.add_employee(
            "Existing Employee", 40, "Senior"
        )

        database.add_task(
            "Existing Task",
            5,
            "2030-01-01",
            "Medium",
            "Easy",
            employee_id,
        )

    def test_reset_removes_existing_records(self):
        """Reset removes all employee and task records."""
        reset_db.reset_database()

        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_reset_recreates_required_tables(self):
        """Reset creates the required database tables."""
        reset_db.reset_database()

        with closing(sqlite3.connect(self.db_path)) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table'"
            ).fetchall()

        tables = {row[0] for row in rows}

        self.assertIn("employees", tables)
        self.assertIn("tasks", tables)

    def test_reset_database_remains_functional(self):
        """The replacement database supports new records."""
        reset_db.reset_database()

        employee_id = database.add_employee(
            "New Employee", 30, "Mid"
        )

        database.add_task(
            "New Task",
            4,
            "2030-01-01",
            "Medium",
            "Easy",
            employee_id,
        )

        self.assertEqual(len(database.get_employees()), 1)
        self.assertEqual(len(database.get_tasks()), 1)

    def test_reset_creates_missing_database(self):
        """Reset initializes a database when none exists."""
        self.db_path.unlink()

        reset_db.reset_database()

        self.assertTrue(self.db_path.exists())
        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_repeated_reset(self):
        """Repeated resets leave a valid empty database."""
        reset_db.reset_database()
        reset_db.reset_database()

        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_missing_schema_preserves_database(self):
        """A missing schema does not destroy existing data."""
        original_data = self.db_path.read_bytes()

        missing_schema = (
            Path(self.temp_dir.name) / "missing.sql"
        )

        with patch.object(
            reset_db, "schema_path", missing_schema
        ):
            with self.assertRaises(FileNotFoundError):
                reset_db.reset_database()

        self.assertEqual(
            self.db_path.read_bytes(), original_data
        )

    def test_invalid_schema_preserves_database(self):
        """Invalid SQL does not destroy existing data."""
        original_data = self.db_path.read_bytes()

        invalid_schema = (
            Path(self.temp_dir.name) / "invalid.sql"
        )

        invalid_schema.write_text(
            "INVALID SQL STATEMENT;",
            encoding="utf-8",
        )

        with patch.object(
            reset_db, "schema_path", invalid_schema
        ):
            with self.assertRaises(sqlite3.OperationalError):
                reset_db.reset_database()

        self.assertEqual(
            self.db_path.read_bytes(), original_data
        )

    def test_connection_failure_preserves_database(self):
        """Connection failure leaves the original database intact."""
        original_data = self.db_path.read_bytes()

        with patch(
            "backend.reset_db.sqlite3.connect",
            side_effect=sqlite3.OperationalError(
                "Connection failed."
            ),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                reset_db.reset_database()

        self.assertEqual(
            self.db_path.read_bytes(), original_data
        )

    def test_replacement_failure_preserves_database(self):
        """A failed file replacement preserves existing data."""
        original_data = self.db_path.read_bytes()

        with patch.object(
            Path,
            "replace",
            side_effect=PermissionError("Access denied."),
        ):
            with self.assertRaises(PermissionError):
                reset_db.reset_database()

        self.assertEqual(
            self.db_path.read_bytes(), original_data
        )

    def test_temporary_files_removed_after_success(self):
        """Successful reset cleans up temporary files."""
        reset_db.reset_database()

        self.assertEqual(
            set(Path(self.temp_dir.name).iterdir()),
            {self.db_path},
        )

    def test_temporary_files_removed_after_failure(self):
        """Failed replacement cleans up temporary files."""
        with patch.object(
            Path,
            "replace",
            side_effect=PermissionError("Access denied."),
        ):
            with self.assertRaises(PermissionError):
                reset_db.reset_database()

        self.assertEqual(
            set(Path(self.temp_dir.name).iterdir()),
            {self.db_path},
        )

    @patch("builtins.input", return_value="RESET")
    def test_confirmed_reset(self, mock_input):
        """Explicit confirmation permits database reset."""
        self.assertEqual(reset_db.main(), 0)

        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_incorrect_confirmation_preserves_database(self):
        """Only the exact confirmation word permits reset."""
        original_data = self.db_path.read_bytes()

        for confirmation in ("", "reset", "Reset", "NO", " RESET "):
            with self.subTest(confirmation=confirmation):
                with patch(
                    "builtins.input",
                    return_value=confirmation,
                ):
                    self.assertEqual(reset_db.main(), 0)

                self.assertEqual(
                    self.db_path.read_bytes(), original_data
                )

    @patch("builtins.input", side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_cancels_reset(self, mock_input):
        """Interrupted confirmation preserves existing data."""
        original_data = self.db_path.read_bytes()

        self.assertEqual(reset_db.main(), 0)

        self.assertEqual(
            self.db_path.read_bytes(), original_data
        )

    @patch("builtins.input", side_effect=EOFError)
    def test_eof_cancels_reset(self, mock_input):
        """Unavailable input cancels the reset."""
        original_data = self.db_path.read_bytes()

        self.assertEqual(reset_db.main(), 0)

        self.assertEqual(
            self.db_path.read_bytes(), original_data
        )

    @patch("builtins.input", return_value="RESET")
    @patch(
        "backend.reset_db.reset_database",
        side_effect=PermissionError("Access denied."),
    )
    def test_os_error_returns_failure(
        self, mock_reset, mock_input
    ):
        """Filesystem errors return exit code one."""
        self.assertEqual(reset_db.main(), 1)

    @patch("builtins.input", return_value="RESET")
    @patch(
        "backend.reset_db.reset_database",
        side_effect=sqlite3.OperationalError(
            "Database error."
        ),
    )
    def test_database_error_returns_failure(
        self, mock_reset, mock_input
    ):
        """Database errors return exit code one."""
        self.assertEqual(reset_db.main(), 1)

    @patch("builtins.input", return_value="NO")
    def test_script_entry_point(self, mock_input):
        """Direct execution exits safely when reset is declined."""
        with patch("sqlite3.connect") as mock_connect:
            with self.assertRaises(SystemExit) as context:
                runpy.run_path(
                    str(Path(reset_db.__file__).resolve()),
                    run_name="__main__",
                )

        self.assertEqual(context.exception.code, 0)
        mock_connect.assert_not_called()

    @unittest.skipUnless(os.name == "posix", "POSIX permissions only")
    def test_reset_database_has_restricted_permissions(self):
        """Reset replaces the database with an owner-only file."""
        self.db_path.chmod(0o644)

        reset_db.reset_database()

        permissions = stat.S_IMODE(self.db_path.stat().st_mode)

        self.assertEqual(permissions, 0o600)


if __name__ == "__main__":
    unittest.main()