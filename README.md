# TaskFlow AI

TaskFlow AI helps managers assign tasks based on employee availability, experience, and workload. The Streamlit dashboard shows deadlines, workload, and fairness metrics. Managers can review Gemini's recommendations and approve changes through the FastAPI backend, which saves assignments in SQLite.

## Set up the alpha

### 1. Install dependencies

Open a terminal in the repository root, the folder that contains `backend/`, `frontend/`, and `requirements.txt`. GitHub Actions uses Python 3.12. SQLite comes with Python.

**macOS and Linux**

```sh
python3.12 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the backend, frontend, and test dependencies with the virtual environment active.

```sh
python -m pip install -r requirements.txt
```

### 2. Initialize the database

```sh
python -m backend.init_db
```

This creates the tables in `backend/taskflow.db`. To load sample employees and tasks into an empty database, run `python -m backend.seed_db`. The sample tasks use fixed deadlines, so add a task with a future deadline to try a new assignment.

### 3. Configure Gemini for recommendations

To enable **Generate AI Recommendations**, get a Gemini API key in Google AI Studio. [Gemini API key guide](https://ai.google.dev/gemini-api/docs/api-key)

Save your key in the plain-text file `backend/.env` using the format below.

```dotenv
GEMINI_API_KEY=your_key_here
```

Keep this file local. Recommendation generation sends employee, task, and workload data to Gemini. Use sample records for the alpha demo. The employee, task, and workload screens work without an API key.

### 4. Start the backend and frontend

Start FastAPI in the first terminal with the virtual environment active.

```sh
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Check the [API health endpoint](http://127.0.0.1:8000/health) for `{"status":"ok"}`. The [interactive API docs](http://127.0.0.1:8000/docs) show the available endpoints.

Open a second terminal in the same repository folder. Activate the existing `.venv` and start Streamlit.

```sh
python -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501
```

Open [TaskFlow AI](http://127.0.0.1:8501) in your browser. Keep both terminals running while you use the app. Press **Ctrl+C** in each terminal to stop its server.

## Try the alpha

1. In **Employees**, open **Add Employee** and save a sample employee with 40 available hours per week.
2. In **Tasks**, open **Add Task** and save an **Easy** task estimated at 2 hours. Use a due date at least a week from today and leave it **Unassigned**.
3. Reload the page and confirm that the employee and task still appear. On the **Dashboard**, check the employee and active task counts.
4. With a Gemini key configured, click **Generate AI Recommendations** on the **Dashboard**. Review **Assignment Impact**, then click **Apply** on a valid suggestion to select it for review.
5. Review **Selected Changes** and click **Approve Selected Changes** when enabled. In **Tasks**, confirm that the **Assigned To** column shows the approved employee.

## Run the tests

Run the test suite from the repository root with the virtual environment active.

```sh
python -m unittest discover -s tests -v
```

The tests use temporary databases and mock Gemini responses. You can run them before starting the servers. GitHub Actions installs the same requirements and runs the same command.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Streamlit cannot load employee, task, or workload data | Check that FastAPI is running at `http://127.0.0.1:8000`. If you changed its address, set `TASKFLOW_API_URL` in the frontend terminal before starting Streamlit. |
| The API reports that the database is unavailable | Run `python -m backend.init_db` from the repository root. |
| Recommendation generation reports a missing Gemini key | Check the `GEMINI_API_KEY` entry in `backend/.env`, then restart FastAPI. |

See the [API endpoint reference](docs/API_ENDPOINT_REFERENCE.md) for request and response examples.
