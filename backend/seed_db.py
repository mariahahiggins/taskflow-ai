from datetime import date, timedelta

from backend.database import (
    add_employee,
    add_task,
    get_employees,
    get_tasks,
)


def seed_database():
    # Avoid inserting data into a populated database
    if get_employees() or get_tasks():
        print("Database already contains data. Seeding skipped.")
        return

    today = date.today()

    # Create sample employees and save their IDs
    sarah_id = add_employee("Sarah", 40, "Senior")
    james_id = add_employee("James", 30, "Mid")
    alex_id = add_employee("Alex", 20, "Junior")

    # Create sample tasks with relative deadlines
    add_task(
        "Prepare project report", 12,
        (today + timedelta(days=3)).isoformat(),
        "High", "Medium", sarah_id
    )

    add_task(
        "Review documentation", 6,
        (today + timedelta(days=3)).isoformat(),
        "Medium", "Easy", sarah_id
    )

    add_task(
        "Update database", 15,
        (today - timedelta(days=3)).isoformat(),
        "High", "Hard", james_id
    )

    add_task(
        "Test application", 8,
        (today + timedelta(days=1)).isoformat(),
        "Medium", "Medium", james_id
    )

    add_task(
        "Organize project files", 5,
        (today + timedelta(days=7)).isoformat(),
        "Low", "Easy", alex_id
    )

    add_task(
        "Design new feature", 10,
        (today + timedelta(days=14)).isoformat(),
        "High", "Hard"
    )

    print("Sample employees and tasks added successfully!")


if __name__ == "__main__":
    seed_database()