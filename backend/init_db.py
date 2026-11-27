"""Initialize the TaskFlow AI database."""

import sqlite3
from pathlib import Path
from contextlib import closing

backend_dir = Path(__file__).resolve().parent

database_path = backend_dir / "taskflow.db"
schema_path = backend_dir / "schema.sql"


def initialize_database():
    """Create the database tables without removing existing data."""
    with closing(sqlite3.connect(database_path)) as connection:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(
                schema_path.read_text(encoding="utf-8")
            )

    print("TaskFlow AI database initialized successfully!")


if __name__ == "__main__":
    initialize_database()