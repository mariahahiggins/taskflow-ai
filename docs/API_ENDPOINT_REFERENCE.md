# TaskFlow AI — API Endpoint Reference

**Backend:** FastAPI  
**Frontend:** Streamlit  
**Database:** SQLite

## 1. Overview

This document describes the employee, task, and workload endpoints for TaskFlow AI.

- **Streamlit** sends requests to FastAPI to retrieve or update information.
- **FastAPI (`main.py`)** receives requests, calls the appropriate Python functions, and returns results.

## 2. Endpoints

### Employees

| Method | Endpoint | Purpose | Python Function |
|---|---|---|---|
| GET | `/employees` | List employees | `get_employees()` |
| GET | `/employees/{id}` | Get one employee | `get_employee()` |
| POST | `/employees` | Add employee | `add_employee()` |
| PUT | `/employees/{id}` | Edit employee | `update_employee()` |

**Employee fields:**

```json
{
  "employee_id": 1,
  "name": "Sarah",
  "available_hours": 40,
  "experience_level": "Mid"
}
```

When adding an employee, Streamlit sends the name, available hours, and experience level. The database generates the employee ID.

### Tasks

| Method | Endpoint | Purpose | Python Function |
|---|---|---|---|
| GET | `/tasks` | List tasks | `get_tasks()` |
| GET | `/tasks/{id}` | Get one task | `get_task()` |
| POST | `/tasks` | Add task | `add_task()` |
| PUT | `/tasks/{id}` | Edit task, assignment, or status | `update_task()` |

**Task fields:**

```json
{
  "task_id": 1,
  "title": "Prepare report",
  "estimated_hours": 10,
  "deadline": "2026-11-05",
  "priority": "High",
  "difficulty": "Medium",
  "status": "Active",
  "employee_id": 1
}
```

**Notes:**
- New tasks default to Active.
- Tasks can be unassigned (`employee_id: null`).
- Completed tasks are excluded from outstanding workload calculations.
- Editing a task can also change its assigned employee or completion status.

### Workloads

| Method | Endpoint | Purpose | Python Functions |
|---|---|---|---|
| GET | `/employees/{id}/workload` | Get one employee's workload | `get_employee_workload_summary()` |
| GET | `/workloads` | Get team totals, employee workloads, fairness, and deadlines | `get_team_workload_summary()` |

#### Individual workload response

| Fields | Meaning |
| --- | --- |
| `employee_id`, `name`, `experience_level`, `available_hours` | Employee details and weekly available hours |
| `outstanding_hours`, `active_task_count` | Estimated hours and count of active assigned tasks |
| `overdue_task_count`, `within_1_week_count`, `week_2_count`, `after_2_weeks_count` | Counts in separate deadline groups |
| `one_week_utilization`, `two_week_utilization` | Percent of available hours needed by each horizon. Returns `null` when capacity is zero. |
| `deadline_conflicts` | Overdue tasks and capacity shortfalls. Each entry includes `deadline`, `required_hours`, `available_hours`, `shortfall_hours`, and `type` (`overdue` or `capacity`). |

Returns HTTP 404 if the employee ID does not exist.

#### Team workload response

| Fields | Meaning |
| --- | --- |
| `total_employees`, `active_tasks`, `unassigned_tasks` | Number of employees, assigned active tasks, and unassigned active tasks |
| `outstanding_hours`, `overdue_tasks` | Assigned active hours and assigned overdue task count |
| `employees_with_conflicts`, `total_deadline_conflicts` | Employees with a conflict and total number of conflict entries |
| `employees` | List of individual workload summaries |
| `fairness` | One- and two-week utilization spreads, plus per-employee counts and hours for active high-priority and Hard tasks and their spreads |
| `upcoming_deadlines` | Active task records sorted by deadline, including overdue and unassigned tasks |

The `high_priority_tasks` and `difficult_tasks` fairness fields map employee IDs
to `count` and `hours`. JSON object keys are strings. A spread is `null` when
there are fewer than two eligible employees.

The API uses the server's local date. Deadline groups separate overdue work,
tasks due within seven days, tasks due from eight through fourteen days, and
later tasks. Capacity includes weekdays from today through the deadline or
horizon date, with weekly availability spread across five working days.
Utilization and deadline conflict checks include unfinished overdue work.

## 3. Future AI Endpoints

These will be finalized during AI integration.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/recommendations` | Generate AI task assignment suggestions |
| POST | `/recommendations/approve` | Apply a manager-approved suggestion |

AI recommendations must be approved by a manager before changing task assignments.
