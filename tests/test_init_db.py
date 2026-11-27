"""Automated tests for database initialization."""

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import closing
import runpy

from backend import init_db, database


class TestDatabaseInitialization(unittest.TestCase):

    def setUp(self):
        """Create an isolated database for each test."""
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

    def test_creates_database(self):
        """Initialization creates a database file."""
        self.assertFalse(self.db_path.exists())

        init_db.initialize_database()

        self.assertTrue(self.db_path.exists())

    def test_creates_required_tables(self):
        """Initialization creates employees and tasks tables."""
        init_db.initialize_database()

        with closing(sqlite3.connect(self.db_path)) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table'"
            ).fetchall()

        tables = {row[0] for row in rows}

        self.assertIn("employees", tables)
        self.assertIn("tasks", tables)

    def test_database_initially_empty(self):
        """A fresh database contains no sample records."""
        init_db.initialize_database()

        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_repeated_initialization(self):
        """Initialization can safely execute multiple times."""
        init_db.initialize_database()
        init_db.initialize_database()

        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_preserves_existing_records(self):
        """Reinitialization does not erase employee or task data."""
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

        employees_before = database.get_employees()
        tasks_before = database.get_tasks()

        init_db.initialize_database()

        self.assertEqual(
            database.get_employees(),
            employees_before,
        )
        self.assertEqual(
            database.get_tasks(),
            tasks_before,
        )

    def test_script_entry_point(self):
        """Direct script execution initializes the database."""
        script_path = Path(init_db.__file__).resolve()

        with patch(
            "sqlite3.connect",
            wraps=sqlite3.connect,
        ) as mock_connect:
            # Redirect the connection to the isolated test database.
            real_connect = sqlite3.connect

            with patch.object(
                mock_connect,
                "side_effect",
                lambda *args, **kwargs: mock_connect._mock_wraps(
                    self.db_path, **kwargs
                ),
            ):
                runpy.run_path(
                    str(script_path),
                    run_name="__main__",
                )

        self.assertTrue(self.db_path.exists())
        self.assertEqual(database.get_employees(), [])
        self.assertEqual(database.get_tasks(), [])

    def test_missing_schema_file(self):
        """Initialization fails if the schema is missing."""
        missing_schema = (
            Path(self.temp_dir.name) / "missing.sql"
        )

        with patch.object(
            init_db, "schema_path", missing_schema
        ):
            with self.assertRaises(FileNotFoundError):
                init_db.initialize_database()

    def test_invalid_schema(self):
        """Invalid SQL prevents successful initialization."""
        invalid_schema = (
            Path(self.temp_dir.name) / "invalid.sql"
        )

        invalid_schema.write_text(
            "INVALID SQL STATEMENT;",
            encoding="utf-8",
        )

        with patch.object(
            init_db, "schema_path", invalid_schema
        ):
            with self.assertRaises(sqlite3.OperationalError):
                init_db.initialize_database()

    def test_database_connection_failure(self):
        """Database connection failures are propagated."""
        with patch(
            "backend.init_db.sqlite3.connect",
            side_effect=sqlite3.OperationalError(
                "Unable to open database file."
            ),
        ):
            with self.assertRaises(sqlite3.OperationalError):
                init_db.initialize_database()

        self.assertFalse(self.db_path.exists())


if __name__ == "__main__":
    unittest.main()