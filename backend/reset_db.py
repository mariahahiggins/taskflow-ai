"""Safely reset the TaskFlow AI database."""

import sqlite3
import sys
from pathlib import Path
from contextlib import closing
from tempfile import TemporaryDirectory
import os

backend_dir = Path(__file__).resolve().parent
database_path = backend_dir / "taskflow.db"
schema_path = backend_dir / "schema.sql"


def reset_database():
    """Replace the existing database with an empty database."""

    if not schema_path.is_file():
        raise FileNotFoundError("schema.sql was not found.")

    schema = schema_path.read_text(encoding="utf-8")

    # Create a replacement before modifying the existing database.
    with TemporaryDirectory(dir=database_path.parent) as temp_dir:
        replacement_path = Path(temp_dir) / "taskflow.db"

        # Restrict replacement database permissions on POSIX systems.
        if os.name == "posix":
            replacement_path.touch(mode=0o600)
            replacement_path.chmod(0o600)

        with closing(sqlite3.connect(replacement_path)) as connection:
            with connection:
                connection.execute("PRAGMA foreign_keys = ON")
                connection.executescript(schema)

        # Replace the original only after successful initialization.
        replacement_path.replace(database_path)

    print("TaskFlow AI database reset successfully!")


def main():
    """Confirm and execute the database reset."""

    try:
        confirmation = input(
            "WARNING: Stop TaskFlow AI before resetting. "
            "This will delete all local database data. "
            "Type RESET to continue: "
        )

        if confirmation != "RESET":
            print("Database reset cancelled.")
            return 0

        reset_database()
        return 0

    except (KeyboardInterrupt, EOFError):
        print("\nDatabase reset cancelled.")
        return 0

    except (OSError, sqlite3.Error):
        print("Database reset failed. Review the database and schema files.")
        return 1


if __name__ == "__main__":
    sys.exit(main())