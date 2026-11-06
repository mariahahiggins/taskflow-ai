import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import date
import re

# Locate the SQLite database in the backend folder
DATABASE_PATH = Path(__file__).resolve().parent / "taskflow.db"

def validate_deadline(deadline):
    if not isinstance(deadline, str):
        raise ValueError("Deadline must be a YYYY-MM-DD string.")

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline):
        raise ValueError("Deadline must use YYYY-MM-DD format.")

    try:
        date.fromisoformat(deadline)
    except ValueError:
        raise ValueError("Deadline must be a valid calendar date.") from None

@contextmanager
def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        with connection:
            yield connection
    finally:
        connection.close()


def get_employees():
    with get_connection() as connection:
        cursor = connection.execute(
            "SELECT * FROM employees"
        )
        employees = [dict(row) for row in cursor.fetchall()]

    return employees


def get_employee(employee_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "SELECT * FROM employees WHERE employee_id = ?",
            (employee_id,)
        )
        row = cursor.fetchone()

    return dict(row) if row else None


def add_employee(name, available_hours, experience_level):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO employees (name, available_hours, experience_level)
            VALUES (?, ?, ?)
            """,
            (name, available_hours, experience_level)
        )
        employee_id = cursor.lastrowid

    return employee_id


def update_employee(employee_id, name, available_hours, experience_level):
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE employees
            SET name = ?,
                available_hours = ?,
                experience_level = ?
            WHERE employee_id = ?
            """,
            (name, available_hours, experience_level, employee_id)
        )
        updated = cursor.rowcount > 0

    return updated


def get_tasks():
    with get_connection() as connection:
        cursor = connection.execute(
            "SELECT * FROM tasks"
        )
        tasks = [dict(row) for row in cursor.fetchall()]

    return tasks


def get_task(task_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "SELECT * FROM tasks WHERE task_id = ?",
            (task_id,)
        )
        row = cursor.fetchone()

    return dict(row) if row else None


def get_tasks_by_employee(employee_id):
    with get_connection() as connection:
        cursor = connection.execute(
            "SELECT * FROM tasks WHERE employee_id = ?",
            (employee_id,)
        )
        tasks = [dict(row) for row in cursor.fetchall()]

    return tasks


def add_task(title, estimated_hours, deadline, priority, difficulty, employee_id=None):
    validate_deadline(deadline)

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO tasks (
                title, estimated_hours, deadline,
                priority, difficulty, employee_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (title, estimated_hours, deadline, priority, difficulty, employee_id)
        )
        task_id = cursor.lastrowid

    return task_id


def update_task(task_id, title, estimated_hours, deadline, priority, difficulty, status, employee_id):
    validate_deadline(deadline)
    
    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE tasks
            SET title = ?,
                estimated_hours = ?,
                deadline = ?,
                priority = ?,
                difficulty = ?,
                status = ?,
                employee_id = ?
            WHERE task_id = ?
            """,
            (title, estimated_hours, deadline, priority,
             difficulty, status, employee_id, task_id)
        )
        updated = cursor.rowcount > 0

    return updated