from backend.database import add_employee, add_task, get_employees, get_tasks

def seed_database():
    # Avoid inserting duplicate data
    if get_employees() or get_tasks():
        print("Database already contains data. Seeding skipped.")
        return

    # Create sample employees and save their IDs
    sarah_id = add_employee("Sarah", 40, "Senior")
    james_id = add_employee("James", 30, "Mid")
    alex_id = add_employee("Alex", 20, "Junior")

    # Create sample tasks
    add_task("Prepare project report", 12, "2026-11-20",
             "High", "Medium", sarah_id)

    add_task("Review documentation", 6, "2026-11-20",
             "Medium", "Easy", sarah_id)

    add_task("Update database", 15, "2026-11-12",
             "High", "Hard", james_id)

    add_task("Test application", 8, "2026-11-18",
             "Medium", "Medium", james_id)

    add_task("Organize project files", 5, "2026-11-27",
             "Low", "Easy", alex_id)

    add_task("Design new feature", 10, "2026-12-04",
             "High", "Hard")

    print("Sample employees and tasks added successfully!")


if __name__ == "__main__":
    seed_database()
