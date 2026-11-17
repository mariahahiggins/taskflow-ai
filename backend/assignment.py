from backend import workload


def find_assignment_records(employees, tasks, task_id, employee_id):
    """Find the employee and task referenced by an AI recommendation."""

    employee = next(
        (e for e in employees if e["employee_id"] == employee_id),
        None,
    )

    task = next(
        (t for t in tasks if t["task_id"] == task_id),
        None,
    )

    return employee, task


def validate_assignment_records(employees, tasks, task_id, employee_id):
    """Check that an assignment references a valid employee and active task."""

    employee, task = find_assignment_records(
        employees, tasks, task_id, employee_id
    )

    errors = []

    if employee is None:
        errors.append("Employee does not exist.")
    elif employee.get("status", "Active") != "Active":
        errors.append("Cannot assign a task to an inactive employee.")

    if task is None:
        errors.append("Task does not exist.")
    elif task["status"] != "Active":
        errors.append("Task is already completed.")

    return errors


def validate_experience(employee, task):
    """Check whether employee experience matches task difficulty."""

    errors = []
    warnings = []

    experience = employee["experience_level"]
    difficulty = task["difficulty"]

    if experience == "Junior":
        if difficulty == "Hard":
            errors.append(
                "Junior employees cannot be assigned Hard tasks."
            )
        elif difficulty == "Medium":
            warnings.append(
                "Junior employee assigned a Medium task."
            )

    elif experience == "Mid":
        if difficulty == "Hard":
            warnings.append(
                "Mid employee assigned a Hard task."
            )

    return errors, warnings


def validate_deadline_capacity(employees, tasks, proposed_tasks, today): 
    """Find employees whose deadline capacity worsens after proposed assignments."""

    errors = {}

    for employee in employees:
        if employee.get("status", "Active") != "Active":
            continue

        employee_id = employee["employee_id"]

        current_tasks = [
            task for task in tasks
            if task["employee_id"] == employee_id
            and task["status"] == "Active"
        ]

        updated_tasks = [
            task for task in proposed_tasks
            if task["employee_id"] == employee_id
            and task["status"] == "Active"
        ]

        def effective_deadline(task):
            return workload.get_capacity_deadline(task, today)

        deadlines = sorted({
            effective_deadline(task)
            for task in current_tasks + updated_tasks
        })

        for deadline in deadlines:
            available = workload.calculate_available_hours(employee["available_hours"], today, deadline)

            before_hours = sum(
                task["estimated_hours"]
                for task in current_tasks
                if effective_deadline(task) <= deadline
            )

            after_hours = sum(
                task["estimated_hours"]
                for task in updated_tasks
                if effective_deadline(task) <= deadline
            )

            before_shortfall = max(0, before_hours - available)
            after_shortfall = max(0, after_hours - available)

            if after_shortfall > before_shortfall + 1e-9:
                errors.setdefault(employee_id, []).append(
                    f"Proposed assignments worsen capacity by "
                    f"{after_shortfall - before_shortfall:.1f} hours "
                    f"for deadline {deadline.isoformat()}."
                )

    return errors


def compare_fairness(before, after):
    """Return warnings for fairness metrics that worsen."""
    
    metrics = {
        "one_week_utilization_spread": "One-week workload balance",
        "two_week_utilization_spread": "Two-week workload balance",
        "high_priority_count_spread": "High-priority task distribution",
        "high_priority_hours_spread": "High-priority hours distribution",
        "difficult_count_spread": "Difficult task distribution",
        "difficult_hours_spread": "Difficult task hours distribution"
    }

    warnings = []

    for key, description in metrics.items():
        before_value = before[key]
        after_value = after[key]

        if before_value is None or after_value is None:
            continue

        if after_value > before_value + 1e-9:
            warnings.append(
                f"{description} becomes less balanced."
            )

    return warnings


def validate_fairness(employees, tasks, proposed_tasks, today):
    """Return warnings if proposed assignments worsen team fairness."""
    
    before_summary = workload.get_team_workload_summary(employees, tasks, today)

    after_summary = workload.get_team_workload_summary(employees, proposed_tasks, today)

    return compare_fairness(
        before_summary["fairness"],
        after_summary["fairness"]
    )


def find_duplicate_task_ids(recommendations):
    """Return task IDs appearing in more than one recommendation."""
    
    seen = set()
    duplicates = set()

    for recommendation in recommendations:
        task_id = recommendation["task_id"]

        if task_id in seen:
            duplicates.add(task_id)
        else:
            seen.add(task_id)

    return duplicates


def simulate_recommendations(tasks, recommendations):
    """Return a copy of tasks with multiple recommendations applied."""

    updated_tasks = [task.copy() for task in tasks]

    for recommendation in recommendations:
        task_id = recommendation["task_id"]
        employee_id = recommendation["employee_id"]

        for task in updated_tasks:
            if task["task_id"] == task_id:
                task["employee_id"] = employee_id
                break

    return updated_tasks


def validate_recommendations(employees, tasks, recommendations):
    """Validate AI recommendations before manager approval."""
    
    duplicates = find_duplicate_task_ids(recommendations)
    results = []

    for recommendation in recommendations:
        task_id = recommendation["task_id"]
        employee_id = recommendation["employee_id"]

        errors = []
        warnings = []

        if task_id in duplicates:
            errors.append("Task appears in multiple recommendations.")

        errors.extend(validate_assignment_records(employees, tasks, task_id, employee_id))

        if not errors:
            employee, task = find_assignment_records(employees, tasks, task_id, employee_id)

            experience_errors, experience_warnings = validate_experience(employee, task)

            errors.extend(experience_errors)
            warnings.extend(experience_warnings)

        results.append({
            "task_id": task_id,
            "employee_id": employee_id,
            "reason": recommendation["reason"],
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        })

    return {
        "recommendations": results
    }



def evaluate_selected_changes(employees, tasks, selected_recommendations, today):
    """Evaluate selected assignments before committing changes."""

    validation = validate_recommendations(employees, tasks, selected_recommendations)

    invalid_recommendations = [
        result for result in validation["recommendations"]
        if not result["valid"]
    ]

    if invalid_recommendations:
        return {
            "recommendations": validation["recommendations"],
            "capacity_errors": {},
            "fairness_warnings": [],
            "can_commit": False
        }

    proposed_tasks = simulate_recommendations(tasks, selected_recommendations)

    capacity_errors = validate_deadline_capacity(employees, tasks, proposed_tasks, today)

    fairness_warnings = validate_fairness(employees, tasks, proposed_tasks, today)

    return {
        "recommendations": validation["recommendations"],
        "capacity_errors": capacity_errors,
        "fairness_warnings": fairness_warnings,
        "can_commit": (
            len(selected_recommendations) > 0
            and len(capacity_errors) == 0
        )
    }


def evaluate_individual_recommendation(employees, tasks, recommendation, selected_recommendations, today):
    """Preview one recommendation against the manager's selected changes."""

    validation = validate_recommendations(employees, tasks, [recommendation])["recommendations"][0]

    task_id = recommendation["task_id"]

    is_applied = any(
        selected["task_id"] == task_id
        for selected in selected_recommendations
    )

    result = {
        "task_id": task_id,
        "employee_id": recommendation["employee_id"],
        "reason": recommendation["reason"],
        "applied": is_applied,
        "valid": validation["valid"],
        "errors": validation["errors"],
        "warnings": validation["warnings"],
        "capacity_errors": {},
        "fairness_warnings": []
    }

    if not validation["valid"]:
        return result

    other_selections = [
        selected for selected in selected_recommendations
        if selected["task_id"] != task_id
    ]

    before_tasks = simulate_recommendations(tasks, other_selections)

    after_tasks = simulate_recommendations(before_tasks, [recommendation])

    result["capacity_errors"] = validate_deadline_capacity(employees, before_tasks, after_tasks, today)

    result["fairness_warnings"] = validate_fairness(employees, before_tasks, after_tasks, today)

    return result
