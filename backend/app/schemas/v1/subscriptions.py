from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.v1.common import PaginatedResponse
from app.services.v1.plan_service import normalize_money


class SubscriptionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: int = Field(ge=1)
    start_date: date
    end_date: date
    cycle: str = Field(default="monthly", pattern="^(monthly|yearly)$")
    auto_renew: int = Field(default=1, ge=0, le=1)
    status: int = Field(default=1, ge=0, le=3)


class SubscriptionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: Optional[int] = Field(default=None, ge=1)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    cycle: Optional[str] = Field(default=None, pattern="^(monthly|yearly)$")
    auto_renew: Optional[int] = Field(default=None, ge=0, le=1)


class SubscriptionStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=3)


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    package_id: int
    status: int
    start_date: date
    end_date: date
    cycle: str
    auto_renew: int
    agreed_price: Optional[float] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SubscriptionListResponse(PaginatedResponse):
    items: list[SubscriptionResponse]


class PlatformSubscriptionResponse(SubscriptionResponse):
    """Platform list item. Per-school subscription responses stay SubscriptionResponse."""

    school_name: str
    plan_name: Optional[str] = None


class PlatformSubscriptionListResponse(PaginatedResponse):
    items: list[PlatformSubscriptionResponse]


class SubscriptionExpireResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expired: int


class SubscriptionBillCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period_start: date
    period_end: date
    amount: Optional[float] = Field(default=None, ge=0)
    due_date: Optional[date] = None
    description: Optional[str] = Field(default=None, max_length=255)
    status: int = Field(default=0, ge=0, le=3)

    @field_validator("amount")
    @classmethod
    def _amount_cents(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        try:
            return float(normalize_money(value))
        except ValueError:
            raise ValueError("must be from 0 through 9999999999.99") from None


class SubscriptionBillStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=3)


class SubscriptionBillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    school_id: int
    amount: float
    status: int
    period_start: date
    period_end: date
    due_date: Optional[date] = None
    description: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SubscriptionBillListResponse(PaginatedResponse):
    items: list[SubscriptionBillResponse]


class SubscriptionRenewalResponse(BaseModel):
    """Immutable renewal snapshot. amount is a JSON number, not a decimal string."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    school_id: int
    package_id: int
    plan_name: str
    cycle: str
    amount: float
    period_start: date
    period_end: date
    created_at: datetime


class SubscriptionRenewalListResponse(PaginatedResponse):
    items: list[SubscriptionRenewalResponse]
