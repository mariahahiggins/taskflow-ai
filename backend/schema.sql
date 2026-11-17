PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS employees (
    employee_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
        CHECK (LENGTH(TRIM(name)) > 0),
    available_hours REAL NOT NULL
        CHECK (available_hours >= 0),
    experience_level TEXT NOT NULL
        CHECK (experience_level IN ('Junior', 'Mid', 'Senior')),
    status TEXT NOT NULL DEFAULT 'Active'
        CHECK (status IN ('Active', 'Inactive'))
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL
        CHECK (LENGTH(TRIM(title)) > 0),
    estimated_hours REAL NOT NULL
        CHECK (estimated_hours > 0),
    deadline TEXT NOT NULL
        CHECK (
            deadline GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
        ),
    priority TEXT NOT NULL
        CHECK (priority IN ('Low', 'Medium', 'High')),
    difficulty TEXT NOT NULL
        CHECK (difficulty IN ('Easy', 'Medium', 'Hard')),
    status TEXT NOT NULL DEFAULT 'Active'
        CHECK (status IN ('Active', 'Completed')),
    employee_id INTEGER,
    FOREIGN KEY (employee_id)
        REFERENCES employees(employee_id)
);
