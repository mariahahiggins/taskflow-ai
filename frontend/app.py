import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.ai_integration import generate_task_recommendations
from frontend.api_client import (
    get_employees,
    create_employee,
    get_tasks,
    create_task,
    update_task
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
st.title("TaskFlow AI")
st.caption("AI-assisted task management and workload balancing")

dashboard, employees_tab, tasks_tab = st.tabs(
    ["Dashboard", "Employees", "Tasks"]
)

# DASHBOARD
with dashboard:
    st.header("Employee Workload Overview")

    employees = st.session_state.employees
    tasks = st.session_state.tasks

    active_tasks = sum(
        1 for task in tasks
        if task["Status"] == "Active"
    )

    overdue_tasks = sum(
        1 for task in tasks
        if task["Due Date"] < date.today()
    )


    potential_conflicts = 0

    for employee in employees:
        assigned_hours_7_days = sum(
            task["Hours"] for task in tasks
            if task["Assigned To"] == employee["Name"]
            and date.today() <= task["Due Date"]
            <= date.today() + timedelta(days=7)
        )

        if assigned_hours_7_days > employee["Available Hours"]:
            potential_conflicts += 1

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Employees", len(employees))
    col2.metric("Active Tasks", active_tasks)
    col3.metric("Potential Conflicts", potential_conflicts)
    col4.metric("Overdue Tasks", overdue_tasks)

    st.subheader("Employee Workload and Deadline Status")

 
    workload_rows = []

    for employee in employees:
        name = employee["Name"]

        assigned = [
            task for task in tasks
            if task["Assigned To"] == name
        ]

        due_7 = sum(
            task["Hours"] for task in assigned
            if date.today() <= task["Due Date"]
            <= date.today() + timedelta(days=7)
        )

        due_14 = sum(
            task["Hours"] for task in assigned
            if date.today() + timedelta(days=7) < task["Due Date"]
            <= date.today() + timedelta(days=14)
        )

        due_21 = sum(
            task["Hours"] for task in assigned
            if date.today() + timedelta(days=14) < task["Due Date"]
            <= date.today() + timedelta(days=21)
        )

        workload_rows.append({
            "Employee": name,
            "Available hrs/wk": employee["Available Hours"],
            "Assigned hrs": sum(t["Hours"] for t in assigned),
            "Due 1-7 days": due_7,
            "Due 8-14 days": due_14,
            "Due 15-21 days": due_21
        })

    st.dataframe(
        pd.DataFrame(workload_rows),
        use_container_width=True,
        hide_index=True
    )

    # Check for potential workload overloads

    st.subheader("Workload Warnings")

    warning_count = 0

    for row in workload_rows:
        if row["Due 1-7 days"] > row["Available hrs/wk"]:
            st.warning(
                f'{row["Employee"]} may be overloaded: '
                f'{row["Due 1-7 days"]} hours due in the next '
                f'7 days, but only '
                f'{row["Available hrs/wk"]} hours available per week.'
            )
            warning_count += 1

    if warning_count == 0:
        st.success("No potential workload overloads detected.")


    st.caption(
        "Sample workload display. Final capacity and deadline "
        "conflict calculations will come from the backend."
    )


    left, right = st.columns(2)

    with left:
        st.subheader("Upcoming Task Deadlines")

        upcoming = sorted(tasks, key=lambda task: task["Due Date"])

        for task in upcoming:
            if task["Assigned To"] == "Unassigned":
                st.warning(
                    f'Unassigned task: {task["Task"]}'
                )

        st.dataframe(
            pd.DataFrame(upcoming),
            use_container_width=True,
            hide_index=True
        )

    with right:
        st.subheader("AI Task Recommendations")

        if st.button("Generate AI Recommendations"):

            employee_info = ""

            for employee in st.session_state.employees:
                assigned_hours = 0

                for task in st.session_state.tasks:
                    if task["Assigned To"] == employee["Name"]:
                        if task["Status"] == "Active":
                            assigned_hours += task["Hours"]

                employee_info += (
                    f"Employee ID: {employee['Employee ID']}\n"
                    f"Name: {employee['Name']}\n"
                    f"Experience: {employee['Experience']}\n"
                    f"Available hours: {employee['Available Hours']}\n"
                    f"Existing workload: {assigned_hours}\n\n"
                )

            task_info = ""

            for task in st.session_state.tasks:
                if task["Status"] == "Active":
                    task_info += (
                        f"Task ID: {task['Task ID']}\n"
                        f"Task: {task['Task']}\n"
                        f"Priority: {task['Priority']}\n"
                        f"Difficulty: {task['Difficulty']}\n"
                        f"Deadline: {task['Due Date']}\n"
                        f"Estimated hours: {task['Hours']}\n\n"
                    )

            task_information = employee_info + task_info

            try:
                with st.spinner("Generating recommendations..."):
                    result = generate_task_recommendations(task_information)

                st.session_state.recommendations = result["recommendations"]

            except Exception as error:
                st.error(f"Could not generate recommendations: {error}")

        if "recommendations" in st.session_state:
            for recommendation in st.session_state.recommendations:

                employee_name = ""
                task_name = ""

                for employee in st.session_state.employees:
                    if employee["Employee ID"] == recommendation["employee_id"]:
                        employee_name = employee["Name"]

                for task in st.session_state.tasks:
                    if task["Task ID"] == recommendation["task_id"]:
                        task_name = task["Task"]

                if employee_name and task_name:
                    st.write("---")
                    st.write("**Task:**", task_name)
                    st.write("**Recommended Employee:**", employee_name)
                    st.write("**Reason:**", recommendation["reason"])

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