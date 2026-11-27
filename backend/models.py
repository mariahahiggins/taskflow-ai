"""Request and response data contracts for the TaskFlow AI API."""

import re

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Maximum positive integer supported by SQLite.
MAX_SQLITE_ID = 2**63 - 1


class APIModel(BaseModel):
    """Shared validation rules for API data."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
        allow_inf_nan=False,
    )


class EmployeeCreate(APIModel):
    """Data supplied when creating an employee; the database generates the ID."""

    name: str = Field(min_length=1, max_length=100)
    available_hours: float = Field(ge=0, le=168, strict=True)
    experience_level: Literal["Junior", "Mid", "Senior"]

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Reject embedded control characters in employee names."""
        if any(ord(character) < 32 or 127 <= ord(character) <= 159
               for character in value):
            raise ValueError("Employee name cannot contain control characters.")
        return value


class EmployeeUpdate(EmployeeCreate):
    """A PUT request supplies all four editable employee fields."""

    status: Literal["Active", "Inactive"]


class EmployeeResponse(EmployeeUpdate):
    """Employee data returned by the API, including the saved ID and status."""

    employee_id: int = Field(gt=0, le=MAX_SQLITE_ID, strict=True)


class TaskCreate(APIModel):
    """Data supplied when creating a task; the database generates the ID."""

    title: str = Field(min_length=1, max_length=200)
    estimated_hours: float = Field(gt=0, le=8760, strict=True)
    deadline: date
    priority: Literal["Low", "Medium", "High"]
    difficulty: Literal["Easy", "Medium", "Hard"]
    status: Literal["Active"] = "Active"
    employee_id: int | None = Field(default=None, gt=0, le=MAX_SQLITE_ID, strict=True)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        """Reject embedded control characters in task titles."""
        if any(ord(character) < 32 or 127 <= ord(character) <= 159
               for character in value):
            raise ValueError("Task title cannot contain control characters.")
        return value

    @field_validator("deadline", mode="before")
    @classmethod
    def validate_deadline(cls, value):
        """Require deadlines to use the YYYY-MM-DD format."""
        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value
        ):
            raise ValueError("Deadline must use YYYY-MM-DD format.")

        return value


class TaskUpdate(TaskCreate):
    """A PUT request supplies every editable field, including status/assignment."""

    status: Literal["Active", "Completed"] = Field(...)
    employee_id: int | None = Field(..., gt=0, le=MAX_SQLITE_ID, strict=True)


class TaskResponse(TaskCreate):
    """Task data returned by the API, including the saved ID."""

    status: Literal["Active", "Completed"] = "Active"
    task_id: int = Field(gt=0, le=MAX_SQLITE_ID, strict=True)


class DeadlineConflictResponse(APIModel):
    """An overdue task or a shortfall at an upcoming deadline."""

    deadline: date
    required_hours: float = Field(ge=0)
    available_hours: float = Field(ge=0)
    shortfall_hours: float = Field(gt=0)
    type: Literal["overdue", "capacity"]
    task_title: str | None = None


class EmployeeWorkloadResponse(EmployeeResponse):
    """Capacity and active work assigned to an employee."""

    outstanding_hours: float = Field(ge=0)
    active_task_count: int = Field(ge=0, strict=True)
    overdue_task_count: int = Field(ge=0, strict=True)
    within_1_week_count: int = Field(ge=0, strict=True)
    week_2_count: int = Field(ge=0, strict=True)
    after_2_weeks_count: int = Field(ge=0, strict=True)
    this_week_hours: float = Field(ge=0)
    next_week_hours: float = Field(ge=0)
    later_hours: float = Field(ge=0)
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

    task_id: int = Field(gt=0, le=MAX_SQLITE_ID, strict=True)
    employee_id: int = Field(gt=0, le=MAX_SQLITE_ID, strict=True)
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """Reject unsafe control characters in recommendation reasons."""
        if any(
            (ord(character) < 32 and character not in "\n\r\t")
            or 127 <= ord(character) <= 159
            for character in value
        ):
            raise ValueError(
                "Recommendation reason contains invalid control characters."
            )

        return value


class GeneratedRecommendations(APIModel):
    """Expected structure of recommendations returned by Gemini."""

    recommendations: list[AssignmentRecommendation]


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
