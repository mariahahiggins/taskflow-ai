import streamlit as st
import pandas as pd
from datetime import date, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.ai_integration import generate_task_recommendations

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
         "Status": "Active", "Assigned To": "Unassigned"}
    ]

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

    active_tasks = len(tasks)
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
