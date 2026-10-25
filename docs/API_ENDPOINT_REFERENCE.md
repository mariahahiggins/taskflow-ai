# TaskFlow AI — API Endpoint Reference

**Backend:** FastAPI  
**Frontend:** Streamlit  
**Database:** SQLite

## 1. Overview

This document outlines the proposed API endpoints for TaskFlow AI.

- **Streamlit** sends requests to FastAPI to retrieve or update information.
- **FastAPI (`main.py`)** receives requests, calls the appropriate Python functions, and returns results.

## 2. Proposed Endpoints

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
| GET | `/employees/{id}/workload` | Get one employee's workload | `get_employee()`, `get_tasks_by_employee()`, `get_workload_summary()` |
| GET | `/workloads` | Get all employee workloads | `get_employees()`, `get_tasks()`, `get_workload_summary()` |

**Example workload response:**

```json
{
  "employee_id": 1,
  "name": "Sarah",
  "weekly_available_hours": 40,
  "outstanding_hours": 60,
  "deadline_groups": {
    "within_1_week": 10,
    "within_2_weeks": 20,
    "after_2_weeks": 30
  },
  "deadline_conflicts": [
    {
      "deadline": "2026-10-28",
      "hours_due": 20,
      "available_hours": 16,
      "shortfall": 4
    }
  ]
}
```

**Workload calculations:**
- Outstanding hours = total estimated hours of active assigned tasks. Hours are not reduced as work progresses unless the task estimate is manually updated.
- Deadline groups show hours due within 1 week, during the second week, and after 2 weeks. These are separate groups, not cumulative totals.
- Deadline conflicts compare cumulative task hours due by each actual deadline against estimated available working hours.
- Available hours are estimated using the employee's weekly availability and a five-day workweek.
- These are approximate capacity checks, not detailed schedules.

## 3. Future AI Endpoints

These will be finalized during AI integration.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/recommendations` | Generate AI task assignment suggestions |
| POST | `/recommendations/approve` | Apply a manager-approved suggestion |

AI recommendations must be approved by a manager before changing task assignments.