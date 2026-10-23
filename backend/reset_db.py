from pathlib import Path
import sqlite3

# Locate the backend folder and database files
backend_dir = Path(__file__).resolve().parent
database_path = backend_dir / "taskflow.db"
schema_path = backend_dir / "schema.sql"

# Confirm before deleting any data
confirmation = input(
    "WARNING: This will delete all local database data. "
    "Type RESET to continue: "
)

if confirmation != "RESET":
    print("Database reset cancelled.")
else:
    # Ensure the schema exists before deleting the database
    if not schema_path.is_file():
        print("Error: schema.sql was not found.")
    else:
        # Remove the existing database
        if database_path.exists():
            database_path.unlink()

        # Recreate the database and its tables
        connection = sqlite3.connect(database_path)

        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(
                schema_path.read_text(encoding="utf-8")
            )
            print("TaskFlow AI database reset successfully!")
        finally:
            connection.close()
