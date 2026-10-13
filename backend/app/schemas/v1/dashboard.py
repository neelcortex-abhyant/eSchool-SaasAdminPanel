from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DashboardStatsResponse(BaseModel):
    """Platform counts for GET /api/v1/super-admin/dashboard/stats.

    The existing GET /dashboard response is unchanged.
    """

    model_config = ConfigDict(extra="forbid")

    total_schools: int
    active_schools: int
    inactive_schools: int
    total_students: int
    total_teachers: int
    active_subscriptions: int


class RecentSchoolItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    code: Optional[str] = None
    created_at: Optional[datetime] = None
    status: int
    installed: int
    package_id: Optional[int] = None
    plan_name: Optional[str] = None


class RecentSchoolsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecentSchoolItem]
    limit: int


class RegistrationMonth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: int
    count: int


class RegistrationAnalyticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    total: int
    unscheduled: int
    months: list[RegistrationMonth]


class SchoolStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_schools: int
    inactive_schools: int


class SubscriptionPlanCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: int
    plan_name: Optional[str] = None
    school_count: int


class SubscriptionDistributionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by_plan: list[SubscriptionPlanCount]
    schools_with_active_subscription: int
    schools_without_active_subscription: int


class RecentActivityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    school_id: Optional[int] = None
    created_at: datetime
    title: str
    description: str


class RecentActivitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[RecentActivityItem]


class SuperAdminDashboardResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Legacy keys (Phase 1–2)
    schools: int
    schools_active: int
    packages: int
    packages_active: int
    super_admins: int
    # Phase 7
    schools_inactive: int = 0
    schools_deactivated: int = 0
    students: int = 0
    school_admins: int = 0
    v1_users: int = 0
    plans: int = 0
    plans_active: int = 0
    subscriptions: int = 0
    subscriptions_active: int = 0
    subscriptions_inactive: int = 0
    subscriptions_expired: int = 0
    subscriptions_cancelled: int = 0
    addons: int = 0
    addons_active: int = 0
    addon_assignments_active: int = 0
    bills: int = 0
    bills_pending: int = 0
    bills_paid: int = 0
    bills_overdue: int = 0
    bills_cancelled: int = 0
    bill_amount_total: float = 0.0
    bill_amount_pending: float = 0.0
    bill_amount_paid: float = 0.0
    unavailable_metrics: list[str] = Field(default_factory=list)
