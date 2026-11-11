import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import api_client
import requests

st.set_page_config(
    page_title="TaskFlow AI",
    layout="wide"
)

# Sample employees
if "employees" not in st.session_state:
    st.session_state.employees = [
        {"Employee ID": 1, "Name": "Alex Johnson", "Available Hours": 40,
         "Experience": "Senior"},
        {"Employee ID": 2, "Name": "Taylor Kim", "Available Hours": 40,
         "Experience": "Mid"},
        {"Employee ID": 3, "Name": "Morgan Lee", "Available Hours": 40,
         "Experience": "Mid"},
        {"Employee ID": 4, "Name": "Jordan Smith", "Available Hours": 40,
         "Experience": "Junior"}
    ]

# Sample tasks
if "tasks" not in st.session_state:
    st.session_state.tasks = [
        {"Task ID": 101, "Task": "Website Redesign", "Hours": 16,
         "Due Date": date.today() + timedelta(days=3),
         "Priority": "High", "Difficulty": "Hard",
         "Status": "Active", "Assigned To": "Alex Johnson"},

        {"Task ID": 102, "Task": "API Integration", "Hours": 12,
         "Due Date": date.today() + timedelta(days=5),
         "Priority": "High", "Difficulty": "Hard",
         "Status": "Active", "Assigned To": "Taylor Kim"},

        {"Task ID": 103, "Task": "User Testing", "Hours": 10,
         "Due Date": date.today() + timedelta(days=10),
         "Priority": "Medium", "Difficulty": "Medium",
         "Status": "Active", "Assigned To": "Morgan Lee"},

        {"Task ID": 104, "Task": "Documentation", "Hours": 8,
         "Due Date": date.today() + timedelta(days=18),
         "Priority": "Low", "Difficulty": "Easy",
         "Status": "Active", "Assigned To": "Unassigned"},

        {"Task ID": 105, "Task": "Testing", "Hours": 8,
        "Due Date": date.today() + timedelta(days=18),
        "Priority": "Low", "Difficulty": "Easy",
        "Status": "Active", "Assigned To": "Unassigned"},

        {"Task ID": 106, "Task": "Napping", "Hours": 8,
        "Due Date": date.today() + timedelta(days=18),
        "Priority": "Low", "Difficulty": "Easy",
        "Status": "Active", "Assigned To": "Unassigned"}
    ]

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
        use_container_width=True,
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
                    new_employee_id = 1

                    for employee in st.session_state.employees:
                        if employee["Employee ID"] >= new_employee_id:
                            new_employee_id = employee["Employee ID"] + 1

                    st.session_state.employees.append({
                        "Employee ID": new_employee_id,
                        "Name": name.strip(),
                        "Available Hours": hours,
                        "Experience": experience
                    })

                    st.success("Employee added!")
                    st.rerun()
# TASKS
with tasks_tab:
    st.header("Tasks")

    st.dataframe(
        pd.DataFrame(st.session_state.tasks),
        use_container_width=True,
        hide_index=True
    )

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
            status = st.selectbox(
                "Status", ["Active", "Completed"]
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
                    new_task_id = 1

                    for task in st.session_state.tasks:
                        if task["Task ID"] >= new_task_id:
                            new_task_id = task["Task ID"] + 1

                    st.session_state.tasks.append({
                        "Task ID": new_task_id,
                        "Task": title.strip(),
                        "Hours": hours,
                        "Due Date": deadline,
                        "Priority": priority,
                        "Difficulty": difficulty,
                        "Status": status,
                        "Assigned To": assigned_to
                    })
                    st.success("Task added!")
                    st.rerun()
