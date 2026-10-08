from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.v1.common import PaginatedResponse


class PlanCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=255)
    monthly_price: float = Field(default=0.0, ge=0)
    yearly_price: float = Field(default=0.0, ge=0)
    student_limit: Optional[int] = Field(default=None, ge=0)
    staff_limit: Optional[int] = Field(default=None, ge=0)


class PlanUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=255)
    monthly_price: Optional[float] = Field(default=None, ge=0)
    yearly_price: Optional[float] = Field(default=None, ge=0)
    student_limit: Optional[int] = Field(default=None, ge=0)
    staff_limit: Optional[int] = Field(default=None, ge=0)


class PlanStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=1)


class PlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    description: Optional[str] = None
    status: int
    monthly_price: float = 0.0
    yearly_price: float = 0.0
    student_limit: Optional[int] = None
    staff_limit: Optional[int] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PlanListResponse(PaginatedResponse):
    items: list[PlanResponse]
