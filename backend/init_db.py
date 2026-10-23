import sqlite3
from pathlib import Path

# Locate the backend folder
backend_dir = Path(__file__).resolve().parent

# Define the database and schema file paths
database_path = backend_dir / "taskflow.db"
schema_path = backend_dir / "schema.sql"

# Create the database and execute the schema
with sqlite3.connect(database_path) as connection:
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        schema_path.read_text(encoding="utf-8")
    )

print("TaskFlow AI database initialized successfully!")
