# TaskFlow AI

TaskFlow AI helps managers assign tasks based on employee availability, experience, and workload. The Streamlit dashboard shows deadlines, workload, and fairness metrics. Managers can review Gemini's recommendations and approve changes through the FastAPI backend, which saves assignments in SQLite.

## Technology stack

TaskFlow AI uses Python, FastAPI, SQLite, and Streamlit. FastAPI handles backend API requests, SQLite stores employee and task records, and Streamlit provides the user interface. A hosted Gemini model generates task assignment recommendations, which are validated by the backend before manager approval.

## Project structure

- `backend/` — FastAPI endpoints, SQLite database operations, workload calculations, assignment validation, fairness metrics, and Gemini integration.
- `frontend/` — Streamlit interface and API client.
- `tests/` — Automated unit and integration tests.
- `docs/` — API endpoint reference and supporting documentation.
- `.github/workflows/` — GitHub Actions configuration for automated testing.

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

This creates the tables in `backend/taskflow.db`. To load sample employees and tasks into an empty database, run `python -m backend.seed_db`. To reset the database and reload fresh sample data, run: `python -m backend.reset_db` then `python -m backend.seed_db`. The reset script requires confirmation and permanently deletes existing local employee and task records. The sample tasks use fixed deadlines, so add a task with a future deadline to try a new assignment.

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

The GitHub Actions workflow runs the automated test suite on repository updates and pull requests. The Alpha release passed the configured CI checks.


## Performance testing

A local performance benchmark was conducted against the FastAPI backend using a seeded SQLite database. The benchmark measured response times for employee retrieval, task retrieval, workload calculations, assignment evaluation, and Gemini recommendation generation.

| Endpoint | Requests | Average response time | Successful requests |
|---|---:|---:|---:|
| GET `/employees` | 20 | 15.81 ms | 20/20 |
| GET `/tasks` | 20 | 12.54 ms | 20/20 |
| GET `/workloads` | 20 | 21.73 ms | 20/20 |
| POST `/recommendations/evaluate` | 20 | 16.76 ms | 20/20 |
| POST `/recommendations` | 3 | 1,143.61 ms | 3/3 |

All 83 requests completed successfully. Local backend operations averaged under 22 milliseconds, while Gemini recommendation generation averaged approximately 1.14 seconds, including external API response time.

These results represent preliminary performance measurements from sequential requests in a local development environment using sample data. They do not establish performance under concurrent users or production workloads.

To reproduce the benchmark, start FastAPI, configure Gemini, and run `python benchmark.py` from the repository root. The evaluation test uses a sample task and employee ID, which may need to be updated to match the current database.

The benchmark sends requests to the local API and does not approve or persist task assignments. Gemini generation requests consume API quota.


## Alpha limitations

TaskFlow AI is a locally hosted prototype intended for demonstration and testing.

- The application does not currently include user authentication or role-based access controls.
- Gemini recommendations require an internet connection and a valid API key.
- Recommendation generation sends employee, task, and workload information to an external AI service. Sample data should be used for testing.
- AI recommendations are reviewed and validated by the backend before assignments can be approved and saved.
- Performance testing has been conducted locally with sample data, not under production-scale workloads.


## Troubleshooting

| Symptom | Check |
| --- | --- |
| Streamlit cannot load employee, task, or workload data | Check that FastAPI is running at `http://127.0.0.1:8000`. If you changed its address, set `TASKFLOW_API_URL` in the frontend terminal before starting Streamlit. |
| The API reports that the database is unavailable | Run `python -m backend.init_db` from the repository root. |
| Recommendation generation reports a missing Gemini key | Check the `GEMINI_API_KEY` entry in `backend/.env`, then restart FastAPI. |

See the [API endpoint reference](docs/API_ENDPOINT_REFERENCE.md) for request and response examples.
