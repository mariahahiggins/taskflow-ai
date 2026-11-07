from datetime import date, timedelta

from backend.fairness import calculate_team_fairness

"""Return total estimated hours for active tasks."""
def calculate_outstanding_hours(tasks):
    return sum(
        task["estimated_hours"]
        for task in tasks
        if task["status"] == "Active"
    )

"""
Calculate available working hours between two dates, inclusive.

Assumes a Monday-Friday schedule with weekly hours spread
evenly across five working days.
"""
def calculate_available_hours(weekly_hours, start_date, end_date):
    if weekly_hours < 0:
        raise ValueError("Weekly hours cannot be negative.")

    if end_date < start_date:
        return 0.0

    daily_hours = weekly_hours / 5
    working_days = 0

    current_date = start_date

    while current_date <= end_date:
        if current_date.weekday() < 5:
            working_days += 1

        current_date += timedelta(days=1)

    return working_days * daily_hours

"""
Group active tasks by deadline relative to today.

Categories are mutually exclusive:
overdue, within_1_week, week_2, after_2_weeks.
"""
def group_tasks_by_deadline(tasks, today):
    groups = {
        "overdue": [],
        "within_1_week": [],
        "week_2": [],
        "after_2_weeks": []
    }

    for task in tasks:
        if task["status"] != "Active":
            continue

        deadline = date.fromisoformat(task["deadline"])
        days_until_due = (deadline - today).days

        if days_until_due < 0:
            groups["overdue"].append(task)
        elif days_until_due <= 7:
            groups["within_1_week"].append(task)
        elif days_until_due <= 14:
            groups["week_2"].append(task)
        else:
            groups["after_2_weeks"].append(task)

    return groups

"""Return active task hours due on or before a deadline."""
def calculate_hours_due_by(tasks, deadline):
    total_hours = 0

    for task in tasks:
        if task["status"] != "Active":
            continue

        task_deadline = date.fromisoformat(task["deadline"])

        if task_deadline <= deadline:
            total_hours += task["estimated_hours"]

    return total_hours

"""
Identify overdue tasks and deadlines where the employee
has insufficient working hours to finish assigned tasks.
"""

def check_deadline_conflicts(employee, tasks, today):
    active_tasks = [
        task for task in tasks
        if task["status"] == "Active"
    ]

    conflicts = []

    # Report each overdue task.
    for task in active_tasks:
        deadline = date.fromisoformat(task["deadline"])

        if deadline < today:
            conflicts.append({
                "deadline": task["deadline"],
                "required_hours": task["estimated_hours"],
                "available_hours": 0,
                "shortfall_hours": task["estimated_hours"],
                "type": "overdue"
            })

    # Find upcoming deadlines to check for capacity conflicts.
    upcoming_deadlines = sorted({
        date.fromisoformat(task["deadline"])
        for task in active_tasks
        if date.fromisoformat(task["deadline"]) >= today
    })

    for deadline in upcoming_deadlines:
        # Include overdue tasks because they are still unfinished.
        required_hours = calculate_hours_due_by(active_tasks, deadline)

        available_hours = calculate_available_hours(employee["available_hours"], today, deadline)

        if required_hours > available_hours:
            conflicts.append({
                "deadline": deadline.isoformat(),
                "required_hours": required_hours,
                "available_hours": available_hours,
                "shortfall_hours": required_hours - available_hours,
                "type": "capacity"
            })

    return conflicts

"""
Return active tasks sorted by deadline, earliest first.

Includes overdue and unassigned tasks.
Excludes completed tasks.
"""
def get_upcoming_deadlines(tasks, today):
    active_tasks = [
        task for task in tasks
        if task["status"] == "Active"
    ]

    return sorted(active_tasks, key=lambda task: task["deadline"])

"""
Calculate deadline-based workload demand over one and two weeks.

Percentages include all active tasks due by each horizon,
including overdue tasks.

Returns None for a percentage when the employee has no
available working hours in that period.
"""
def calculate_utilization(employee, tasks, today):
    one_week_end = today + timedelta(days=7)
    two_week_end = today + timedelta(days=14)

    one_week_hours = calculate_hours_due_by(tasks, one_week_end)
    two_week_hours = calculate_hours_due_by(tasks, two_week_end)

    one_week_capacity = calculate_available_hours(employee["available_hours"], today, one_week_end)
    two_week_capacity = calculate_available_hours(employee["available_hours"], today, two_week_end)

    one_week_percentage = (
        (one_week_hours / one_week_capacity) * 100
        if one_week_capacity > 0 else None
    )
    two_week_percentage = (
        (two_week_hours / two_week_capacity) * 100
        if two_week_capacity > 0 else None
    )

    return {
        "one_week": one_week_percentage,
        "two_weeks": two_week_percentage
    }

"""
Calculate a workload summary for one employee.

Filters tasks by employee ID to prevent counting
tasks assigned to other employees or unassigned tasks.
"""
def get_employee_workload_summary(employee, tasks, today):
    employee_tasks = [
        task for task in tasks
        if task["employee_id"] == employee["employee_id"]
    ]

    active_tasks = [
        task for task in employee_tasks
        if task["status"] == "Active"
    ]

    outstanding_hours = calculate_outstanding_hours(employee_tasks)

    deadline_groups = group_tasks_by_deadline(employee_tasks, today)

    utilization = calculate_utilization(employee, employee_tasks, today)

    deadline_conflicts = check_deadline_conflicts(employee, employee_tasks, today)

    return {
        "employee_id": employee["employee_id"],
        "name": employee["name"],
        "experience_level": employee["experience_level"],
        "available_hours": employee["available_hours"],
        "outstanding_hours": outstanding_hours,
        "active_task_count": len(active_tasks),
        "overdue_task_count": len(deadline_groups["overdue"]),
        "within_1_week_count": len(deadline_groups["within_1_week"]),
        "week_2_count": len(deadline_groups["week_2"]),
        "after_2_weeks_count": len(deadline_groups["after_2_weeks"]),
        "one_week_utilization": utilization["one_week"],
        "two_week_utilization": utilization["two_weeks"],
        "deadline_conflicts": deadline_conflicts
    }

"""
Combine individual workload summaries, team totals,
fairness measurements, and upcoming deadlines.

Assigned active tasks contribute to employee workload.
Unassigned active tasks are counted separately.
"""
def get_team_workload_summary(employees, tasks, today):
    employee_summaries = [
        get_employee_workload_summary(employee, tasks, today)
        for employee in employees
    ]

    fairness = calculate_team_fairness(employees, tasks, employee_summaries)

    employee_ids = {
        employee["employee_id"]
        for employee in employees
    }

    assigned_active_tasks = [
        task for task in tasks
        if task["status"] == "Active"
        and task["employee_id"] in employee_ids
    ]

    unassigned_tasks = [
        task for task in tasks
        if task["status"] == "Active"
        and task["employee_id"] is None
    ]

    total_deadline_conflicts = sum(
        len(summary["deadline_conflicts"])
        for summary in employee_summaries
    )

    employees_with_conflicts = sum(
        1 for summary in employee_summaries
        if summary["deadline_conflicts"]
    )

    return {
        "total_employees": len(employees),
        "active_tasks": len(assigned_active_tasks),
        "unassigned_tasks": len(unassigned_tasks),
        "outstanding_hours": sum(
            summary["outstanding_hours"]
            for summary in employee_summaries
        ),
        "overdue_tasks": sum(
            summary["overdue_task_count"]
            for summary in employee_summaries
        ),
        "employees_with_conflicts": employees_with_conflicts,
        "total_deadline_conflicts": total_deadline_conflicts,
        "employees": employee_summaries,
        "fairness": fairness,
        "upcoming_deadlines": get_upcoming_deadlines(tasks, today)
    }
