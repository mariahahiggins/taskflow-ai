"""Employee and task data contracts for the TaskFlow AI API."""

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
    status: Literal["Active", "Completed"] = "Active"
    employee_id: int | None = Field(default=None, gt=0, strict=True)


class TaskUpdate(TaskCreate):
    """A PUT request supplies every editable field, including status/assignment."""

    status: Literal["Active", "Completed"] = Field(...)
    employee_id: int | None = Field(..., gt=0, strict=True)


class TaskResponse(TaskCreate):
    """Task data returned by the API, including the saved ID."""

    task_id: int = Field(gt=0, strict=True)
