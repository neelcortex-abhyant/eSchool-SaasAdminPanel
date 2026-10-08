from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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
