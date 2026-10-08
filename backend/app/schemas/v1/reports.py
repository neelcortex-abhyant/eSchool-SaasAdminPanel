from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.v1.common import PaginatedResponse


class SchoolReportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    code: Optional[str] = None
    status: int
    installed: int
    created_at: Optional[datetime] = None


class SchoolReportResponse(PaginatedResponse):
    items: list[SchoolReportItem]


class SubscriptionReportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    school_id: int
    package_id: int
    status: int
    start_date: date
    end_date: date
    cycle: str


class SubscriptionReportResponse(PaginatedResponse):
    items: list[SubscriptionReportItem]


class BillReportItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    subscription_id: int
    school_id: int
    amount: float
    status: int
    period_start: date
    period_end: date
    due_date: Optional[date] = None


class BillReportResponse(PaginatedResponse):
    items: list[BillReportItem]
    amount_sum: float = Field(description="Sum of amounts for the filtered set (all pages)")
