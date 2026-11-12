import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import requests
from frontend.api_client import (
    get_employees,
    create_employee,
    get_tasks,
    create_task,
    update_task,
    get_workloads,
    generate_recommendations,
    preview_recommendation,
    evaluate_recommendations,
    approve_recommendations
)

st.set_page_config(
    page_title="TaskFlow AI",
    layout="wide"
)

# Load employees from the FastAPI backend
try:
    api_employees = get_employees()

    st.session_state.employees = [
        {
            "Employee ID": employee["employee_id"],
            "Name": employee["name"],
            "Available Hours": employee["available_hours"],
            "Experience": employee["experience_level"]
        }
        for employee in api_employees
    ]

except Exception as error:
    st.error(f"Could not load employees from the backend: {error}")
    if "employees" not in st.session_state:
        st.session_state.employees = []

# Load tasks from FastAPI backend
try:
    api_tasks = get_tasks()

    employee_names = {
        employee["Employee ID"]: employee["Name"]
        for employee in st.session_state.employees
    }

    st.session_state.tasks = [
        {
            "Task ID": task["task_id"],
            "Task": task["title"],
            "Hours": task["estimated_hours"],
            "Due Date": date.fromisoformat(task["deadline"]),
            "Priority": task["priority"],
            "Difficulty": task["difficulty"],
            "Assigned To": employee_names.get(task["employee_id"], "Unassigned"),
            "Status": task["status"]
        }
        for task in api_tasks
    ]

except Exception as error:
    st.error(f"Could not load tasks from the backend: {error}")

    if "tasks" not in st.session_state:
        st.session_state.tasks = []

def compact_fairness_warnings(warnings):
    """Combine related fairness warnings for display."""
    result = []
    high_priority = False
    difficult = False

    for warning in warnings:
        text = warning.lower()

        if "high-priority task distribution" in text or \
           "high-priority hours distribution" in text:
            if not high_priority:
                result.append("High-priority workload distribution becomes less balanced.")
                high_priority = True

        elif "difficult task distribution" in text or \
             "difficult task hours distribution" in text:
            if not difficult:
                result.append("Difficult-task workload distribution becomes less balanced.")
                difficult = True

        else:
            result.append(warning)

    return result


st.title("TaskFlow AI")
st.caption("AI-assisted task management and workload balancing")

dashboard, employees_tab, tasks_tab = st.tabs(
    ["Dashboard", "Employees", "Tasks"]
)

# DASHBOARD
with dashboard:
    st.header("Employee Workload Overview")

    # Get workload data from FastAPI
    try:
        workload_data = api_client.get_workloads()
    except requests.exceptions.RequestException as error:
        st.error(f"Could not load workload data: {error}")
        st.stop()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Employees", workload_data["total_employees"])
    col2.metric("Active Tasks",workload_data["active_tasks"])
    col3.metric("Employees with Conflicts", workload_data["employees_with_conflicts"])
    col4.metric("Overdue Tasks", workload_data["overdue_tasks"])

    st.subheader("Employee Workload and Deadline Status")

    # Build the table using backend workload summaries
    workload_rows = []

    for employee in workload_data["employees"]:
        workload_rows.append({
            "Employee": employee["name"],
            "Available hrs/wk": employee["available_hours"],
            "Assigned hrs": employee["outstanding_hours"],
            "This week": employee["this_week_hours"],
            "Next week": employee["next_week_hours"],
            "Later": employee["later_hours"]
        })

    st.dataframe(
        pd.DataFrame(workload_rows),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Task hours are grouped by due date (Monday–Sunday). "
        "Overdue work is included in This week."
    )

    # Display deadline and capacity warnings from the backend
    st.subheader("Workload Warnings")

    warning_count = 0

    for employee in workload_data["employees"]:
        for conflict in employee["deadline_conflicts"]:

            if conflict["type"] == "overdue":
                st.warning(
                    f'{employee["name"]} has an overdue task '
                    f'due {conflict["deadline"]} '
                    f'({conflict["required_hours"]:g} hours).'
                )

            elif conflict["type"] == "capacity":
                st.warning(
                    f'{employee["name"]} may not have enough time '
                    f'to complete work due by {conflict["deadline"]}: '
                    f'{conflict["required_hours"]:g} hours required, '
                    f'{conflict["available_hours"]:g} hours available '
                    f'({conflict["shortfall_hours"]:g} hours short).'
                )

            warning_count += 1

    if warning_count == 0:
        st.success("No deadline or capacity conflicts detected.")

    # UPCOMING TASK DEADLINES
    st.subheader("Upcoming Task Deadlines")

    # Get active tasks already sorted by deadline by the backend
    upcoming_tasks = workload_data["upcoming_deadlines"]

    # Look up employee names using the workload summaries
    employee_lookup = {
        employee["employee_id"]: employee["name"]
        for employee in workload_data["employees"]
    }

    # Format backend task records for display
    upcoming_rows = []

    for task in upcoming_tasks:
        employee_id = task["employee_id"]

        assigned_to = (
            employee_lookup.get(employee_id, "Unknown")
            if employee_id is not None
            else "Unassigned"
        )

        upcoming_rows.append({
            "Task": task["title"],
            "Hours": task["estimated_hours"],
            "Due Date": task["deadline"],
            "Priority": task["priority"],
            "Difficulty": task["difficulty"],
            "Assigned To": assigned_to
        })

    # Display the first five tasks
    if upcoming_rows:
        st.dataframe(
            pd.DataFrame(upcoming_rows[:5]),
            use_container_width=True,
            hide_index=True
        )

        # Show remaining tasks when more than five exist
        remaining = upcoming_rows[5:]

        if remaining:
            count = len(remaining)
            label = f"Show {count} remaining {'task' if count == 1 else 'tasks'}"

            with st.expander(label):
                st.dataframe(
                    pd.DataFrame(remaining),
                    use_container_width=True,
                    hide_index=True
                )
    else:
        st.info("No active tasks.")

    # AI TASK RECOMMENDATIONS
    st.subheader("AI Task Recommendations")

    if "selected_recommendations" not in st.session_state:
        st.session_state.selected_recommendations = []

    if st.button("Generate AI Recommendations"):
        try:
            with st.spinner("Generating recommendations..."):
                result = api_client.generate_recommendations()

            st.session_state.recommendations = result["recommendations"]
            st.session_state.selected_recommendations = []

        except requests.exceptions.RequestException as error:
            if error.response is not None:
                try:
                    detail = error.response.json().get("detail", str(error))
                except ValueError:
                    detail = str(error)

                st.error(f"Could not generate recommendations: {detail}")
            else:
                st.error(f"Could not connect to the backend: {error}")

    
    if "recommendations" in st.session_state:

        employees = api_client.get_employees()
        db_tasks = api_client.get_tasks()

        employee_lookup = {
            employee["employee_id"]: employee
            for employee in employees
        }

        task_lookup = {
            task["task_id"]: task
            for task in db_tasks
        }

        for recommendation in st.session_state.recommendations:

            task_id = recommendation["task_id"]
            employee_id = recommendation["employee_id"]

            task = task_lookup.get(task_id)
            employee = employee_lookup.get(employee_id)

            if task is None or employee is None:
                st.error("Could not find the task or employee.")
                continue

            is_selected = any(
                selected["task_id"] == task_id
                for selected in st.session_state.selected_recommendations
            )

            # Calculate the proposed assignment's impact
            preview = None

            try:
                preview = api_client.preview_recommendation({
                    "recommendation": {
                        "task_id": task_id,
                        "employee_id": employee_id,
                        "reason": recommendation["reason"]
                    },
                    "selected_recommendations":
                        st.session_state.selected_recommendations
                })

            except requests.exceptions.RequestException:
                st.error(
                    f"Could not calculate assignment impact "
                    f"for {task['title']}."
                )

            with st.container(border=True):

                title_col, status_col = st.columns([4, 1])

                with title_col:
                    st.markdown(f"**{task['title']}**")

                with status_col:
                    if is_selected:
                        st.markdown(
                            "<div style='text-align: right; color: #2563eb; "
                            "font-weight: 600;'>● Selected</div>",
                            unsafe_allow_html=True
                        )

                left_col, right_col = st.columns([3, 2])

                # LEFT: Task and recommendation details
                with left_col:

                    st.caption(
                        f'{task["estimated_hours"]} hrs · '
                        f'{task["priority"]} priority · '
                        f'{task["difficulty"]} · '
                        f'Due {task["deadline"]}'
                    )

                    current_id = task.get("employee_id")

                    if current_id is None:
                        current_name = "Unassigned"
                    else:
                        current_employee = employee_lookup.get(current_id)
                        current_name = (
                            current_employee["name"]
                            if current_employee
                            else "Unknown"
                        )

                    st.markdown(
                        f'**{current_name} → {employee["name"]}**'
                    )

                    st.caption(recommendation["reason"])

                # RIGHT: Validation and assignment impact
                with right_col:

                    st.markdown("**Assignment Impact**")

                    errors = recommendation.get("errors", [])
                    warnings = recommendation.get("warnings", [])

                    if errors:
                        for error in errors:
                            st.markdown(f"❌ {error}")

                    if warnings:
                        for warning in warnings:
                            st.markdown(f"⚠️ {warning}")

                    if not errors and not warnings:
                        st.markdown("✅ Initial validation passed")

                    # Dynamic capacity and fairness feedback
                    if preview is not None:

                        capacity_errors = preview.get(
                            "capacity_errors", {}
                        )

                        fairness_warnings = preview.get(
                            "fairness_warnings", []
                        )

                        for employee_errors in capacity_errors.values():
                            for error in employee_errors:
                                st.markdown(f"❌ {error}")

                        for warning in compact_fairness_warnings(fairness_warnings):
                            st.markdown(f"⚠️ {warning}")

                        if not capacity_errors and not fairness_warnings:
                            if preview.get("valid", False):
                                st.markdown(
                                    "✅ No capacity or fairness issues"
                                )

                    if is_selected:

                        # Undo a temporary selection
                        if st.button(
                            "Undo",
                            key=f"undo_{task_id}",
                            type="secondary"
                        ):

                            st.session_state.selected_recommendations = [
                                selected
                                for selected in st.session_state.selected_recommendations
                                if selected["task_id"] != task_id
                            ]

                            st.rerun()

                    else:

                        # Apply a recommendation temporarily
                        if st.button(
                            "Apply",
                            key=f"apply_{task_id}",
                            type="secondary",
                            disabled=not recommendation.get("valid", False)
                        ):

                            st.session_state.selected_recommendations.append({
                                "task_id": task_id,
                                "employee_id": employee_id,
                                "reason": recommendation["reason"]
                            })

                            st.rerun()

        # SELECTED CHANGES SUMMARY
        selected = st.session_state.selected_recommendations

        if selected:
            st.markdown("#### Selected Changes")

            for change in selected:
                selected_task = task_lookup.get(change["task_id"])
                selected_employee = employee_lookup.get(change["employee_id"])

                if selected_task and selected_employee:
                    st.markdown(
                        f':blue[✓] **{selected_task["title"]}** → '
                        f'{selected_employee["name"]}'
                    )

            # Evaluate all selected changes together
            evaluation = None

            try:
                evaluation = api_client.evaluate_recommendations({
                    "selected_recommendations": selected
                })

            except requests.exceptions.RequestException as error:
                st.error(f"Could not evaluate selected changes: {error}")

            # Display combined evaluation results
            if evaluation is not None:

                capacity_errors = evaluation.get(
                    "capacity_errors", {}
                )

                fairness_warnings = evaluation.get(
                    "fairness_warnings", []
                )

                # Show blocking capacity errors
                all_capacity_errors = [
                    error
                    for employee_errors in capacity_errors.values()
                    for error in employee_errors
                ]

                if all_capacity_errors:
                    count = len(all_capacity_errors)

                    st.markdown(
                        f"❌ {count} blocking capacity "
                        f"{'conflict' if count == 1 else 'conflicts'}"
                    )

                    for error in all_capacity_errors:
                        st.caption(error)

                # Count grouped fairness warnings
                compact_warnings = compact_fairness_warnings(fairness_warnings)

                if compact_warnings:
                    count = len(compact_warnings)

                    st.markdown(
                        f"⚠️ {count} fairness "
                        f"{'warning' if count == 1 else 'warnings'}"
                    )

                if evaluation.get("can_commit", False):
                    st.markdown("✅ Selected changes are ready for approval.")
                else:
                    st.markdown(
                        "❌ Selected changes cannot be approved "
                        "until blocking issues are resolved."
                    )

            # Final approval
            can_approve = (
                evaluation is not None
                and evaluation.get("can_commit", False)
            )

            st.markdown("""
                <style>
                .st-key-approve_selected button:not(:disabled) {
                    background-color: #2563eb;
                    color: white;
                    border-color: #2563eb;
                }

                .st-key-approve_selected button:not(:disabled):hover {
                    background-color: #1d4ed8;
                    border-color: #1d4ed8;
                    color: white;
                }
                </style>
            """, unsafe_allow_html=True)

            if st.button(
                "Approve Selected Changes",
                key="approve_selected",
                type="secondary",
                disabled=not can_approve
            ):
                try:
                    result = api_client.approve_recommendations({
                        "selected_recommendations": selected
                    })

                    # Clear temporary selections and old recommendations
                    st.session_state.selected_recommendations = []
                    st.session_state.recommendations = []

                    st.success(result["message"])
                    st.rerun()

                except requests.exceptions.RequestException as error:
                    st.error(f"Could not approve changes: {error}")

            st.caption(
                f"{len(selected)} recommendation(s) selected. "
                "No database changes have been saved."
            )






# EMPLOYEES
with employees_tab:
    st.header("Employees")

    st.dataframe(
        pd.DataFrame(st.session_state.employees),
        width="stretch",
        hide_index=True
    )

    with st.expander("Add Employee"):
        with st.form("employee_form"):
            name = st.text_input("Employee Name")

            hours = st.number_input(
                "Available Hours per Week",
                min_value=1,
                max_value=168,
                value=40
            )

            experience = st.selectbox(
                "Experience Level",
                ["Junior", "Mid", "Senior"]
            )

            submitted = st.form_submit_button("Save Employee")

            if submitted:
                if not name.strip():
                    st.error("Enter an employee name.")

                elif any(
                    e["Name"].casefold() == name.strip().casefold()
                    for e in st.session_state.employees
                ):
                    st.error("That employee already exists.")

                else:
                    employee_data = {
                        "name": name.strip(),
                        "available_hours": float(hours),
                        "experience_level": experience
                    }

                    try:
                        result = create_employee(employee_data)

                        st.success(
                            f'{result["name"]} was successfully added!'
                        )
                        st.rerun()

                    except Exception as error:
                        st.error(f"Could not add employee: {error}")
# TASKS
with tasks_tab:
    st.header("Tasks")

    st.dataframe(
        pd.DataFrame(st.session_state.tasks),
        use_container_width=True,
        hide_index=True
    )

    # Edit tasks
    with st.expander("Edit Existing Tasks"):

        if st.session_state.tasks:

            task_options = {
                f'{task["Task ID"]} - {task["Task"]}': task["Task ID"]
                for task in st.session_state.tasks
            }

            selected_task = st.selectbox(
                "Choose a task",
                list(task_options.keys())
            )

            selected_task_id = task_options[selected_task]

            task_to_edit = next(
                task for task in st.session_state.tasks
                if task["Task ID"] == selected_task_id
            )

            with st.container(border=True):
                with st.form("edit_task_form"):

                    edited_title = st.text_input(
                        "Task Name",
                        value=task_to_edit["Task"]
                    )

                    edited_hours = st.number_input(
                        "Estimated Hours",
                        min_value=1,
                        max_value=1000,
                        value=int(task_to_edit["Hours"])
                    )

                    edited_deadline = st.date_input(
                        "Due Date",
                        value=task_to_edit["Due Date"]
                    )

                    edited_priority = st.selectbox(
                        "Priority",
                        ["Low", "Medium", "High"],
                        index=["Low", "Medium", "High"].index(
                            task_to_edit["Priority"]
                        )
                    )

                    edited_difficulty = st.selectbox(
                        "Difficulty",
                        ["Easy", "Medium", "Hard"],
                        index=["Easy", "Medium", "Hard"].index(
                            task_to_edit["Difficulty"]
                        )
                    )

                    employee_names = ["Unassigned"] + [
                        employee["Name"]
                        for employee in st.session_state.employees
                    ]

                    edited_employee = st.selectbox(
                        "Assigned To",
                        employee_names,
                        index=employee_names.index(
                            task_to_edit["Assigned To"]
                        )
                    )

                    edited_status = st.selectbox(
                        "Status",
                        ["Active", "Completed"],
                        index=["Active", "Completed"].index(
                            task_to_edit["Status"]
                        )
                    )

                    save_task = st.form_submit_button("Save Changes")

                    if save_task:
                        if not edited_title.strip():
                            st.error("Please enter a task name.")
                        else:
                            employee_id = next(
                                (
                                    employee["Employee ID"]
                                    for employee in st.session_state.employees
                                    if employee["Name"] == edited_employee
                                ),
                                None
                            )

                            task_data = {
                                "title": edited_title.strip(),
                                "estimated_hours": float(edited_hours),
                                "deadline": edited_deadline.isoformat(),
                                "priority": edited_priority,
                                "difficulty": edited_difficulty,
                                "status": edited_status,
                                "employee_id": employee_id
                            }

                            try:
                                update_task(selected_task_id, task_data)
                                st.success("Task updated successfully!")
                                st.rerun()

                            except Exception as error:
                                st.error(f"Could not update task: {error}")
        else:
            st.info("No tasks available to edit.")


    with st.expander("Add Task"):
        with st.form("task_form"):
            title = st.text_input("Task Name")
            hours = st.number_input(
                "Estimated Hours",
                min_value=1,
                max_value=1000,
                value=8
            )
            deadline = st.date_input(
                "Due Date",
                value=date.today() + timedelta(days=7),
                min_value=date.today()
            )
            priority = st.selectbox(
                "Priority", ["Low", "Medium", "High"]
            )
            difficulty = st.selectbox(
                "Difficulty", ["Easy", "Medium", "Hard"]
            )

            names = ["Unassigned"] + [
                e["Name"] for e in st.session_state.employees
            ]
            assigned_to = st.selectbox("Assign Employee", names)

            submitted = st.form_submit_button("Save Task")

            if submitted:
                if not title.strip():
                    st.error("Enter a task name.")
                else:
                    employee_id = next(
                        (
                            employee["Employee ID"]
                            for employee in st.session_state.employees
                            if employee["Name"] == assigned_to
                        ),
                        None
                    )

                    task_data = {
                        "title": title.strip(),
                        "estimated_hours": float(hours),
                        "deadline": deadline.isoformat(),
                        "priority": priority,
                        "difficulty": difficulty,
                        "employee_id": employee_id
                    }

                    try:
                        result = create_task(task_data)
                        st.success(
                            f'Task "{result["title"]}" was successfully added!'
                        )
                        st.rerun()

                    except Exception as error:
                        st.error(f"Could not add task: {error}")