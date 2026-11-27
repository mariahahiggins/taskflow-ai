"""Automated tests for database initialization."""

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import closing
import runpy
import os
import stat

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

        isolated_script = Path(self.temp_dir.name) / "init_db.py"
        isolated_schema = Path(self.temp_dir.name) / "schema.sql"

        isolated_script.write_bytes(script_path.read_bytes())
        isolated_schema.write_bytes(init_db.schema_path.read_bytes())

        runpy.run_path(
            str(isolated_script),
            run_name="__main__",
        )

        created_database = Path(self.temp_dir.name) / "taskflow.db"

        self.assertTrue(created_database.exists())

        with patch.object(database, "DATABASE_PATH", created_database):
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

        if os.name == "posix":
            self.assertTrue(self.db_path.exists())
            self.assertEqual(self.db_path.stat().st_size, 0)
        else:
            self.assertFalse(self.db_path.exists())

    @unittest.skipUnless(os.name == "posix", "POSIX permissions only")
    def test_new_database_has_restricted_permissions(self):
        """New databases permit only owner read/write access."""
        init_db.initialize_database()
        permissions = stat.S_IMODE(self.db_path.stat().st_mode)
        self.assertEqual(permissions, 0o600)

    @unittest.skipUnless(os.name == "posix", "POSIX permissions only")
    def test_existing_database_permissions_are_corrected(self):
        """Initialization restricts existing database permissions."""
        init_db.initialize_database()
        self.db_path.chmod(0o644)
        init_db.initialize_database()
        permissions = stat.S_IMODE(self.db_path.stat().st_mode)
        self.assertEqual(permissions, 0o600)


if __name__ == "__main__":
    unittest.main()