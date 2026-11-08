import os
import json
from pathlib import Path
from dotenv import load_dotenv
from google import genai


load_dotenv(Path(__file__).resolve().parent / ".env")

def generate_task_recommendations(task_information):

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from the .env file.")

    client = genai.Client(api_key=api_key

    prompt = f"""
You are helping a manager assign tasks to employees.

Use the employee and task information below to recommend
who should work on each task.

Look at experience, available hours, current workload,
task difficulty, and deadlines.

Rules:
- Junior employees should get Easy tasks.
- Junior employees can get Medium tasks, but include a warning.
- Junior employees should not get Hard tasks.
- Mid employees can get Easy and Medium tasks.
- Mid employees can get Hard tasks with a warning.
- Senior employees can get any task.

Do not recommend someone who does not have enough available
hours or the experience needed for the task.

Employee and task information:

{task_information}

Return the results in this JSON format:

{{
    "recommendations": [
        {{
            "task_id": 6,
            "employee_id": 2,
            "reason": "Explain why this employee was selected."
        }}
    ]
}}

Return JSON only. Do not include extra text.
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config={
            "response_mime_type": "application/json"
        }
    )

    return json.loads(response.text)


if __name__ == "__main__":

    print("\nTest 1 - Normal task recommendations:")

    test_task = """
EMPLOYEES:

Employee ID: 1
Name: Alex
Experience: Junior
Available hours: 20
Existing workload: 5

Employee ID: 2
Name: Taylor
Experience: Mid
Available hours: 15
Existing workload: 4

Employee ID: 3
Name: Morgan
Experience: Senior
Available hours: 25
Existing workload: 8

TASKS:

Task ID: 101
Task: Create project documentation
Priority: High
Difficulty: Easy
Deadline: 2026-11-10
Estimated hours: 4

Task ID: 102
Task: Design application interface
Priority: Medium
Difficulty: Medium
Deadline: 2026-11-12
Estimated hours: 6

Task ID: 103
Task: Develop database integration
Priority: High
Difficulty: Hard
Deadline: 2026-11-09
Estimated hours: 8

Task ID: 104
Task: Review website content
Priority: Low
Difficulty: Easy
Deadline: 2026-11-15
Estimated hours: 3
"""

    result = generate_task_recommendations(test_task)
    print(json.dumps(result, indent=4))


    print("\nTest 2 - Employee experience level:")

    test_experience = """
EMPLOYEES:

Employee ID: 1
Name: Alex
Experience: Junior
Available hours: 20
Existing workload: 2

TASKS:

Task ID: 105
Task: Build the database integration
Priority: High
Difficulty: Hard
Deadline: 2026-11-12
Estimated hours: 8
"""

    result = generate_task_recommendations(test_experience)
    print(json.dumps(result, indent=4))


    print("\nTest 3 - Available hours:")

    test_hours = """
EMPLOYEES:

Employee ID: 1
Name: Alex
Experience: Junior
Available hours: 3
Existing workload: 2

TASKS:

Task ID: 106
Task: Create project documentation
Priority: High
Difficulty: Easy
Deadline: 2026-11-12
Estimated hours: 8
"""

    result = generate_task_recommendations(test_hours)
    print(json.dumps(result, indent=4))


    print("\nTest 4 - Experience level warning:")

    test_warning = """
EMPLOYEES:

Employee ID: 1
Name: Alex
Experience: Junior
Available hours: 20
Existing workload: 2

TASKS:

Task ID: 107
Task: Design application interface
Priority: Medium
Difficulty: Medium
Deadline: 2026-11-12
Estimated hours: 6
"""

    result = generate_task_recommendations(test_warning)
    print(json.dumps(result, indent=4))


    print("\nTest 5 - Mid employee with Hard task warning:")

    test_mid_warning = """
EMPLOYEES:

Employee ID: 2
Name: Taylor
Experience: Mid
Available hours: 20
Existing workload: 3

TASKS:

Task ID: 108
Task: Develop database integration
Priority: High
Difficulty: Hard
Deadline: 2026-11-12
Estimated hours: 8
"""

    result = generate_task_recommendations(test_mid_warning)
    print(json.dumps(result, indent=4))