from datetime import date, timedelta

from backend.fairness import calculate_team_fairness


def get_capacity_deadline(task, today):
    """Use the current workweek for overdue task capacity checks."""
    deadline = date.fromisoformat(task["deadline"])

    if deadline >= today:
        return deadline

    days_until_friday = (4 - today.weekday()) % 7
    return today + timedelta(days=days_until_friday)


def calculate_outstanding_hours(tasks):
    """Return total estimated hours for active tasks."""
    return sum(
        task["estimated_hours"]
        for task in tasks
        if task["status"] == "Active"
    )


def calculate_available_hours(weekly_hours, start_date, end_date):
    """
    Calculate available working hours between two dates, inclusive.

    Assumes a Monday-Friday schedule with weekly hours spread
    evenly across five working days.
    """
    if weekly_hours < 0:
        raise ValueError("Weekly hours cannot be negative.")

    if end_date < start_date:
        return 0.0

    daily_hours = weekly_hours / 5
    total_days = (end_date - start_date).days + 1

    full_weeks, remaining_days = divmod(total_days, 7)
    working_days = full_weeks * 5

    for offset in range(remaining_days):
        if (start_date.weekday() + offset) % 7 < 5:
            working_days += 1

    return working_days * daily_hours


def group_tasks_by_deadline(tasks, today):
    """
    Group active tasks by deadline relative to today.

    Categories are mutually exclusive:
    overdue, within_1_week, week_2, after_2_weeks.
    """
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


def group_task_hours_by_calendar_week(tasks, today):
    """
    Group active task hours into calendar weeks.

    This week includes overdue tasks and tasks due through Sunday.
    Next week includes tasks due the following Monday through Sunday.
    Later includes tasks due after next Sunday.
    """
    this_sunday = today + timedelta(days=6 - today.weekday())
    next_sunday = this_sunday + timedelta(days=7)

    hours = {
        "this_week": 0.0,
        "next_week": 0.0,
        "later": 0.0
    }

    for task in tasks:
        if task["status"] != "Active":
            continue

        deadline = date.fromisoformat(task["deadline"])
        estimated_hours = task["estimated_hours"]

        if deadline <= this_sunday:
            hours["this_week"] += estimated_hours
        elif deadline <= next_sunday:
            hours["next_week"] += estimated_hours
        else:
            hours["later"] += estimated_hours

    return hours


def calculate_hours_due_by(tasks, deadline):
    """Return active task hours due on or before a deadline."""
    total_hours = 0

    for task in tasks:
        if task["status"] != "Active":
            continue

        task_deadline = date.fromisoformat(task["deadline"])

        if task_deadline <= deadline:
            total_hours += task["estimated_hours"]

    return total_hours


def check_deadline_conflicts(employee, tasks, today):
    """
    Identify overdue tasks and deadlines where the employee
    has insufficient working hours to finish assigned tasks.
    """
    active_tasks = [
        task for task in tasks
        if task["status"] == "Active"
    ]

    conflicts = []

    for task in active_tasks:
        deadline = date.fromisoformat(task["deadline"])

        if deadline < today:
            conflicts.append({
                "task_title": task.get("title"),
                "deadline": task["deadline"],
                "required_hours": task["estimated_hours"],
                "available_hours": 0,
                "shortfall_hours": task["estimated_hours"],
                "type": "overdue"
            })

    
    capacity_tasks = [
        {
            **task,
            "deadline": get_capacity_deadline(task, today).isoformat()
        }
        for task in active_tasks
    ]

    upcoming_deadlines = sorted({
        date.fromisoformat(task["deadline"])
        for task in capacity_tasks
    })

    for deadline in upcoming_deadlines:
        required_hours = calculate_hours_due_by(capacity_tasks, deadline)

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


def get_upcoming_deadlines(tasks, today):
    """
    Return active tasks sorted by deadline, earliest first.

    Includes overdue and unassigned tasks.
    Excludes completed tasks.
    """
    active_tasks = [
        task for task in tasks
        if task["status"] == "Active"
    ]

    return sorted(active_tasks, key=lambda task: task["deadline"])


def calculate_utilization(employee, tasks, today):
    """
    Calculate deadline-based workload demand over one and two weeks.

    Percentages include all active tasks due by each horizon,
    including overdue tasks.

    Returns None for a percentage when the employee has no
    available working hours in that period.
    """
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


def get_employee_workload_summary(employee, tasks, today):
    """
    Calculate a workload summary for one employee.

    Filters tasks by employee ID to prevent counting
    tasks assigned to other employees or unassigned tasks.
    """
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

    calendar_week_hours = group_task_hours_by_calendar_week(employee_tasks, today)

    utilization = calculate_utilization(employee, employee_tasks, today)

    deadline_conflicts = check_deadline_conflicts(employee, employee_tasks, today)

    return {
        "employee_id": employee["employee_id"],
        "name": employee["name"],
        "experience_level": employee["experience_level"],
        "available_hours": employee["available_hours"],
        "status": employee.get("status", "Active"),
        "outstanding_hours": outstanding_hours,
        "active_task_count": len(active_tasks),
        "overdue_task_count": len(deadline_groups["overdue"]),
        "within_1_week_count": len(deadline_groups["within_1_week"]),
        "week_2_count": len(deadline_groups["week_2"]),
        "after_2_weeks_count": len(deadline_groups["after_2_weeks"]),
        "this_week_hours": calendar_week_hours["this_week"],
        "next_week_hours": calendar_week_hours["next_week"],
        "later_hours": calendar_week_hours["later"],
        "one_week_utilization": utilization["one_week"],
        "two_week_utilization": utilization["two_weeks"],
        "deadline_conflicts": deadline_conflicts
    }


def get_team_workload_summary(employees, tasks, today):
    """
    Combine individual workload summaries, team totals,
    fairness measurements, and upcoming deadlines.

    Assigned active tasks contribute to employee workload.
    Unassigned active tasks are counted separately.
    """

    active_employees = [
        employee for employee in employees
        if employee.get("status", "Active") == "Active"
    ]

    employee_summaries = [
        get_employee_workload_summary(employee, tasks, today)
        for employee in active_employees
    ]

    fairness = calculate_team_fairness(active_employees, tasks, employee_summaries)

    employee_ids = {
        employee["employee_id"]
        for employee in active_employees
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
        "total_employees": len(active_employees),
        "active_tasks": len(assigned_active_tasks) + len(unassigned_tasks),
        "unassigned_tasks": len(unassigned_tasks),
        "outstanding_hours": sum(
            summary["outstanding_hours"]
            for summary in employee_summaries
        ),
        "overdue_tasks": sum(
            1 for task in tasks
            if task["status"] == "Active"
            and date.fromisoformat(task["deadline"]) < today
        ),
        "employees_with_conflicts": employees_with_conflicts,
        "total_deadline_conflicts": total_deadline_conflicts,
        "employees": employee_summaries,
        "fairness": fairness,
        "upcoming_deadlines": get_upcoming_deadlines(tasks, today)
    }
