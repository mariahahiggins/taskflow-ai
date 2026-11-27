"""FastAPI endpoints for the local TaskFlow AI prototype."""

import sqlite3
import json
from datetime import date
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from pydantic import ValidationError
from google.genai import errors as genai_errors

from backend import database, workload, assignment, ai_integration
from backend.models import (
    MAX_SQLITE_ID,
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
    EmployeeWorkloadResponse,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TeamWorkloadResponse,
    RecommendationBatchResponse,
    IndividualPreviewRequest,
    IndividualPreviewResponse,
    SelectedChangesRequest,
    SelectedChangesResponse,
    ApprovalResponse,
    GeneratedRecommendations
)

app = FastAPI(
    title="TaskFlow AI API",
    description="Employee, task, and workload management for the local TaskFlow AI prototype.",
    version="0.1.0",
)

DATABASE_UNAVAILABLE_DETAIL = (
    "Database unavailable. Confirm it has been initialized and try again."
)


def require_initialized_database() -> None:
    """Require the database file created by init_db.py before accessing records."""
    if not FilePath(database.DATABASE_PATH).is_file():
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_DETAIL)


data_routes = APIRouter(dependencies=[Depends(require_initialized_database)])

@app.exception_handler(RequestValidationError)
async def request_validation_error(request: Request, exc: RequestValidationError):
    """Return validation errors without exposing raw input values."""
    errors = [
        {
            "type": error["type"],
            "loc": list(error["loc"]),
            "msg": error["msg"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=422,
        content={"detail": errors},
    )


@app.exception_handler(sqlite3.IntegrityError)
async def database_constraint_error(request: Request, exc: sqlite3.IntegrityError):
    detail = "The data violates a database constraint."
    if getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_CONSTRAINT_FOREIGNKEY:
        detail = "The assigned employee does not exist."
    return JSONResponse(status_code=400, content={"detail": detail})


@app.exception_handler(sqlite3.OperationalError)
async def database_unavailable(request: Request, exc: sqlite3.OperationalError):
    return JSONResponse(
        status_code=503,
        content={"detail": DATABASE_UNAVAILABLE_DETAIL},
    )


@app.get("/", tags=["Status"])
def root() -> dict[str, str]:
    return {"message": "TaskFlow AI backend is running."}


@app.get("/health", tags=["Status"])
def health_check() -> dict[str, str]:
    """Confirm that the API process is responding."""
    return {"status": "ok"}


@data_routes.get("/employees", response_model=list[EmployeeResponse], tags=["Employees"])
def list_employees():
    return sorted(database.get_employees(), key=lambda employee: employee["employee_id"])


@data_routes.get("/employees/{id}", response_model=EmployeeResponse, tags=["Employees"])
def get_employee(id: Annotated[int, Path(gt=0, le=MAX_SQLITE_ID)]):
    employee = database.get_employee(id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee


@data_routes.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Employees"],
)
def create_employee(employee: EmployeeCreate):
    values = employee.model_dump()
    employee_id = database.add_employee(**values)
    return {"employee_id": employee_id, "status": "Active", **values}


@data_routes.put("/employees/{id}", response_model=EmployeeResponse, tags=["Employees"])
def update_employee(id: Annotated[int, Path(gt=0, le=MAX_SQLITE_ID)], employee: EmployeeUpdate):
    """Replace all editable employee fields."""
    values = employee.model_dump()
    if not database.update_employee(id, **values):
        raise HTTPException(status_code=404, detail="Employee not found.")
    return {"employee_id": id, **values}


@data_routes.get("/tasks", response_model=list[TaskResponse], tags=["Tasks"])
def list_tasks():
    return sorted(database.get_tasks(), key=lambda task: task["task_id"])


@data_routes.get("/tasks/{id}", response_model=TaskResponse, tags=["Tasks"])
def get_task(id: Annotated[int, Path(gt=0, le=MAX_SQLITE_ID)]):
    task = database.get_task(id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@data_routes.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Tasks"],
)
def create_task(task: TaskCreate):
    values = task.model_dump(mode="json", exclude={"status"})
    try:
        task_id = database.add_task(**values)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc
    return {"task_id": task_id, "status": task.status, **values}


@data_routes.put("/tasks/{id}", response_model=TaskResponse, tags=["Tasks"])
def update_task(id: Annotated[int, Path(gt=0, le=MAX_SQLITE_ID)], task: TaskUpdate):
    """Replace all editable task fields, including status and assignment."""
    values = task.model_dump(mode="json")
    try:
        updated = database.update_task(id, **values)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc)
        ) from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found.")
    return {"task_id": id, **values}


@data_routes.get(
    "/employees/{id}/workload",
    response_model=EmployeeWorkloadResponse,
    tags=["Workloads"],
)
def get_employee_workload(id: Annotated[int, Path(gt=0, le=MAX_SQLITE_ID)]):
    """Report active work, utilization, and deadline conflicts for one employee."""
    employee = get_employee(id)
    tasks = database.get_tasks_by_employee(id)
    return workload.get_employee_workload_summary(employee, tasks, date.today())


@data_routes.get(
    "/workloads", response_model=TeamWorkloadResponse, tags=["Workloads"]
)
def get_team_workload():
    """Report team workload, fairness metrics, and upcoming deadlines."""
    employees = database.get_employees()
    tasks = database.get_tasks()
    return workload.get_team_workload_summary(employees, tasks, date.today())


@data_routes.post(
    "/recommendations",
    response_model=RecommendationBatchResponse,
    tags=["Recommendations"],
)
def generate_recommendations():
    """Generate and validate AI task recommendations."""

    today = date.today()

    employees = database.get_employees()
    tasks = database.get_tasks()

    if not any(employee["status"] == "Active" for employee in employees):
        return {"recommendations": []}

    eligible_tasks = [
        task for task in tasks
        if task["status"] == "Active"
    ]

    if not eligible_tasks:
        return {"recommendations": []}

    summary = workload.get_team_workload_summary(employees, tasks, today)

    task_information = ai_integration.format_task_information(
        employees,
        tasks,
        summary,
        [task["task_id"] for task in eligible_tasks]
    )

    try:
        result = ai_integration.generate_task_recommendations(task_information)

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned invalid JSON."
        ) from exc

    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned an invalid recommendation format."
        ) from exc
    
    except ValueError as exc:
        if "GEMINI_API_KEY is missing" in str(exc):
            raise HTTPException(
                status_code=503,
                detail="Gemini API key is not configured."
            ) from exc

        raise HTTPException(
            status_code=502,
            detail="Gemini returned an invalid response."
        ) from exc
    
    except genai_errors.APIError as exc:
        print("AI: Gemini API request failed.", flush=True)

        raise HTTPException(
            status_code=502,
            detail="Gemini API request failed."
        ) from exc

    try:
        validated_result = GeneratedRecommendations.model_validate(result)

        recommendations = [
            item.model_dump()
            for item in validated_result.recommendations
        ]

    except (ValidationError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Gemini returned an invalid recommendation format."
        ) from exc

    
    eligible_ids = {task["task_id"] for task in eligible_tasks}
    task_lookup = {task["task_id"]: task for task in tasks}

    filtered_recommendations = []
    seen_task_ids = set()

    for recommendation in recommendations:
        task_id = recommendation["task_id"]
        employee_id = recommendation["employee_id"]

        if task_id not in eligible_ids:
            raise HTTPException(
            status_code=502,
            detail="Gemini recommended a task that is not eligible."
        )

        if task_id in seen_task_ids:
            continue

        task = task_lookup[task_id]

        if task["employee_id"] == employee_id:
            continue

        seen_task_ids.add(task_id)
        filtered_recommendations.append(recommendation)

    return assignment.validate_recommendations(employees, tasks, filtered_recommendations)



@data_routes.post(
    "/recommendations/preview",
    response_model=IndividualPreviewResponse,
    tags=["Recommendations"],
)
def preview_recommendation(request: IndividualPreviewRequest):
    """Preview one recommendation alongside the manager's selected assignments."""

    today = date.today()

    employees = database.get_employees()
    tasks = database.get_tasks()

    recommendation = request.recommendation.model_dump()

    selected_recommendations = [
        item.model_dump()
        for item in request.selected_recommendations
    ]

    return assignment.evaluate_individual_recommendation(
        employees,
        tasks,
        recommendation,
        selected_recommendations,
        today
    )


@data_routes.post(
    "/recommendations/evaluate",
    response_model=SelectedChangesResponse,
    tags=["Recommendations"],
)
def evaluate_recommendations(request: SelectedChangesRequest):
    """Evaluate all manager-selected assignments before approval."""

    today = date.today()

    employees = database.get_employees()
    tasks = database.get_tasks()

    selected_recommendations = [
        recommendation.model_dump()
        for recommendation in request.selected_recommendations
    ]

    return assignment.evaluate_selected_changes(
        employees,
        tasks,
        selected_recommendations,
        today,
    )


@data_routes.post(
    "/recommendations/approve",
    response_model=ApprovalResponse,
    tags=["Recommendations"],
)
def approve_recommendations(request: SelectedChangesRequest):
    """Validate and save manager-approved task assignments."""

    today = date.today()

    selected_recommendations = [
        item.model_dump()
        for item in request.selected_recommendations
    ]

    if not selected_recommendations:
        raise HTTPException(
            status_code=400,
            detail="No recommendations selected for approval."
        )

    employees = database.get_employees()
    tasks = database.get_tasks()

    evaluation = assignment.evaluate_selected_changes(
        employees,
        tasks,
        selected_recommendations,
        today,
    )

    if not evaluation["can_commit"]:
        raise HTTPException(
            status_code=400,
            detail="Selected recommendations failed validation."
        )

    try:
        updated_task_ids = database.approve_assignments(selected_recommendations)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc)
        ) from exc

    return {
        "message": "Selected task assignments approved successfully.",
        "updated_task_ids": updated_task_ids,
    }

app.include_router(data_routes)
