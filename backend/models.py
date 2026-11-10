"""Request and response data contracts for the TaskFlow AI API."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Shared validation rules for API data."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        allow_inf_nan=False,
    )


class EmployeeCreate(APIModel):
    """Data supplied when creating an employee; the database generates the ID."""

    name: str = Field(min_length=1)
    available_hours: float = Field(ge=0, strict=True)
    experience_level: Literal["Junior", "Mid", "Senior"]


class EmployeeUpdate(EmployeeCreate):
    """A PUT request supplies all three editable employee fields."""


class EmployeeResponse(EmployeeCreate):
    """Employee data returned by the API, including the saved ID."""

    employee_id: int = Field(gt=0, strict=True)


class TaskCreate(APIModel):
    """Data supplied when creating a task; the database generates the ID."""

    title: str = Field(min_length=1)
    estimated_hours: float = Field(gt=0, strict=True)
    deadline: date
    priority: Literal["Low", "Medium", "High"]
    difficulty: Literal["Easy", "Medium", "Hard"]
    status: Literal["Active"] = "Active"
    employee_id: int | None = Field(default=None, gt=0, strict=True)


class TaskUpdate(TaskCreate):
    """A PUT request supplies every editable field, including status/assignment."""

    status: Literal["Active", "Completed"] = Field(...)
    employee_id: int | None = Field(..., gt=0, strict=True)


class TaskResponse(TaskCreate):
    """Task data returned by the API, including the saved ID."""

    status: Literal["Active", "Completed"] = "Active"
    task_id: int = Field(gt=0, strict=True)


class DeadlineConflictResponse(APIModel):
    """An overdue task or a shortfall at an upcoming deadline."""

    deadline: date
    required_hours: float = Field(ge=0)
    available_hours: float = Field(ge=0)
    shortfall_hours: float = Field(gt=0)
    type: Literal["overdue", "capacity"]


class EmployeeWorkloadResponse(EmployeeResponse):
    """Capacity and active work assigned to an employee."""

    outstanding_hours: float = Field(ge=0)
    active_task_count: int = Field(ge=0, strict=True)
    overdue_task_count: int = Field(ge=0, strict=True)
    within_1_week_count: int = Field(ge=0, strict=True)
    week_2_count: int = Field(ge=0, strict=True)
    after_2_weeks_count: int = Field(ge=0, strict=True)
    one_week_utilization: float | None = Field(ge=0)
    two_week_utilization: float | None = Field(ge=0)
    deadline_conflicts: list[DeadlineConflictResponse]


class TaskDistributionResponse(APIModel):
    """The count and estimated hours in one employee's task category."""

    count: int = Field(ge=0, strict=True)
    hours: float = Field(ge=0)


class TeamFairnessResponse(APIModel):
    """Utilization spreads and the current distribution of challenging work."""

    one_week_utilization_spread: float | None = Field(ge=0)
    two_week_utilization_spread: float | None = Field(ge=0)
    high_priority_tasks: dict[int, TaskDistributionResponse]
    high_priority_count_spread: int | None = Field(ge=0, strict=True)
    high_priority_hours_spread: float | None = Field(ge=0)
    difficult_tasks: dict[int, TaskDistributionResponse]
    difficult_count_spread: int | None = Field(ge=0, strict=True)
    difficult_hours_spread: float | None = Field(ge=0)


class TeamWorkloadResponse(APIModel):
    """Team workload totals, individual summaries, fairness, and active deadlines."""

    total_employees: int = Field(ge=0, strict=True)
    active_tasks: int = Field(ge=0, strict=True)
    unassigned_tasks: int = Field(ge=0, strict=True)
    outstanding_hours: float = Field(ge=0)
    overdue_tasks: int = Field(ge=0, strict=True)
    employees_with_conflicts: int = Field(ge=0, strict=True)
    total_deadline_conflicts: int = Field(ge=0, strict=True)
    employees: list[EmployeeWorkloadResponse]
    fairness: TeamFairnessResponse
    upcoming_deadlines: list[TaskResponse]


class AssignmentRecommendation(APIModel):
    """One assignment suggested by Gemini."""

    task_id: int = Field(gt=0, strict=True)
    employee_id: int = Field(gt=0, strict=True)
    reason: str = Field(min_length=1)


class ValidatedRecommendation(AssignmentRecommendation):
    """A recommendation with its validation results."""

    valid: bool
    errors: list[str]
    warnings: list[str]


class RecommendationBatchResponse(APIModel):
    """Recommendations returned after generation and validation."""
    recommendations: list[ValidatedRecommendation]


class IndividualPreviewRequest(APIModel):
    """One recommendation and the manager's selected changes."""

    recommendation: AssignmentRecommendation
    selected_recommendations: list[AssignmentRecommendation]


class IndividualPreviewResponse(ValidatedRecommendation):
    """Individual recommendation preview results."""

    applied: bool
    capacity_errors: dict[int, list[str]]
    fairness_warnings: list[str]


class SelectedChangesRequest(APIModel):
    """Assignments currently selected by the manager."""

    selected_recommendations: list[AssignmentRecommendation]


class SelectedChangesResponse(APIModel):
    """Results of evaluating all selected assignments."""

    recommendations: list[ValidatedRecommendation]
    capacity_errors: dict[int, list[str]]
    fairness_warnings: list[str]
    can_commit: bool


class ApprovalResponse(APIModel):
    """Confirmation that assignments were saved."""
    
    message: str
    updated_task_ids: list[int]
