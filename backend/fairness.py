"""
Calculate the difference between the highest and lowest
employee utilization percentages for a given period.

Excludes employees with None utilization.
Returns None if fewer than two employees have valid values.
"""
def calculate_utilization_spread(employee_summaries, period):
    if period not in ("one_week", "two_week"):
        raise ValueError("Invalid utilization period")

    key = f"{period}_utilization"

    utilizations = [
        employee[key]
        for employee in employee_summaries
        if employee[key] is not None
    ]

    if len(utilizations) < 2:
        return None

    return max(utilizations) - min(utilizations)

"""    
Count active high-priority tasks and their estimated
hours for each employee.

Excludes completed and unassigned tasks.
Includes employees with no high-priority tasks.
"""
def count_high_priority_tasks(employees, tasks):
    counts = {
        employee["employee_id"]: {
            "count": 0,
            "hours": 0
        }
        for employee in employees
    }

    for task in tasks:
        if task["status"] != "Active":
            continue

        if task["priority"] != "High":
            continue

        employee_id = task["employee_id"]

        if employee_id not in counts:
            continue

        counts[employee_id]["count"] += 1
        counts[employee_id]["hours"] += task["estimated_hours"]

    return counts

"""
Count active Hard tasks and their estimated hours
for each employee.

Excludes completed and unassigned tasks.
Includes employees with no Hard tasks.
"""
def count_difficult_tasks(employees, tasks):
    counts = {
        employee["employee_id"]: {
            "count": 0,
            "hours": 0
        }
        for employee in employees
    }

    for task in tasks:
        if task["status"] != "Active":
            continue

        if task["difficulty"] != "Hard":
            continue

        employee_id = task["employee_id"]

        if employee_id not in counts:
            continue

        counts[employee_id]["count"] += 1
        counts[employee_id]["hours"] += task["estimated_hours"]

    return counts

"""
Calculate team-wide fairness measurements.

Compares employee utilization, high-priority work,
and difficult work across the team.
"""
def calculate_team_fairness(employees, tasks, employee_summaries):
    one_week_spread = calculate_utilization_spread(employee_summaries, "one_week")

    two_week_spread = calculate_utilization_spread(employee_summaries, "two_week")

    high_priority = count_high_priority_tasks(employees, tasks)

    difficult = count_difficult_tasks(employees, tasks)

    def calculate_distribution_spread(distribution, field):
        values = [
            employee[field]
            for employee in distribution.values()
        ]

        if len(values) < 2:
            return None

        return max(values) - min(values)

    return {
        "one_week_utilization_spread": one_week_spread,
        "two_week_utilization_spread": two_week_spread,

        "high_priority_tasks": high_priority,
        "high_priority_count_spread":
            calculate_distribution_spread(
                high_priority, "count"
            ),
        "high_priority_hours_spread":
            calculate_distribution_spread(
                high_priority, "hours"
            ),

        "difficult_tasks": difficult,
        "difficult_count_spread":
            calculate_distribution_spread(
                difficult, "count"
            ),
        "difficult_hours_spread":
            calculate_distribution_spread(
                difficult, "hours"
            )
    }
