"""Super Admin platform dashboard — DB-backed SaaS metrics (Phase 7)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import (
    Addon,
    AddonSubscription,
    Package,
    School,
    Student,
    Subscription,
    SubscriptionBill,
)
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN, ROLE_USER
from app.models.v1.user import User
from app.services.v1.subscription_service import (
    BILL_STATUS_CANCELLED,
    BILL_STATUS_OVERDUE,
    BILL_STATUS_PAID,
    BILL_STATUS_PENDING,
    SUB_STATUS_ACTIVE,
    SUB_STATUS_CANCELLED,
    SUB_STATUS_EXPIRED,
    SUB_STATUS_INACTIVE,
)


def _count(db: Session, stmt) -> int:
    return int(db.scalar(stmt) or 0)


def _sum(db: Session, stmt) -> float:
    value = db.scalar(stmt)
    return float(value or 0)


def platform_dashboard(db: Session) -> dict:
    """Aggregate platform metrics from existing tables only.

    Legacy keys (schools, schools_active, packages, packages_active, super_admins)
    remain for Phase 1–2 clients. New Phase 7 keys are additive.
    """
    schools_total = _count(
        db, select(func.count()).select_from(School).where(School.deleted_at.is_(None))
    )
    schools_active = _count(
        db,
        select(func.count())
        .select_from(School)
        .where(School.deleted_at.is_(None), School.status == 1),
    )
    schools_inactive = _count(
        db,
        select(func.count())
        .select_from(School)
        .where(School.deleted_at.is_(None), School.status == 0),
    )
    schools_deactivated = _count(
        db,
        select(func.count())
        .select_from(School)
        .where(School.deleted_at.is_(None), School.status == 0, School.installed == 0),
    )

    packages_total = _count(
        db, select(func.count()).select_from(Package).where(Package.deleted_at.is_(None))
    )
    packages_active = _count(
        db,
        select(func.count())
        .select_from(Package)
        .where(Package.deleted_at.is_(None), Package.status == 1),
    )

    students_total = _count(
        db, select(func.count()).select_from(Student).where(Student.deleted_at.is_(None))
    )

    super_admins = _count(
        db, select(func.count()).select_from(User).where(User.role == ROLE_SUPER_ADMIN)
    )
    school_admins = _count(
        db, select(func.count()).select_from(User).where(User.role == ROLE_SCHOOL_ADMIN)
    )
    v1_users = _count(
        db, select(func.count()).select_from(User).where(User.role == ROLE_USER)
    )

    def sub_count(status: int) -> int:
        return _count(
            db,
            select(func.count())
            .select_from(Subscription)
            .where(Subscription.deleted_at.is_(None), Subscription.status == status),
        )

    subscriptions_total = _count(
        db,
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.deleted_at.is_(None)),
    )

    addons_total = _count(
        db, select(func.count()).select_from(Addon).where(Addon.deleted_at.is_(None))
    )
    addons_active = _count(
        db,
        select(func.count())
        .select_from(Addon)
        .where(Addon.deleted_at.is_(None), Addon.status == 1),
    )
    addon_assignments_active = _count(
        db,
        select(func.count())
        .select_from(AddonSubscription)
        .where(AddonSubscription.deleted_at.is_(None), AddonSubscription.status == 1),
    )

    def bill_count(status: int) -> int:
        return _count(
            db,
            select(func.count())
            .select_from(SubscriptionBill)
            .where(SubscriptionBill.deleted_at.is_(None), SubscriptionBill.status == status),
        )

    def bill_amount(status: int | None = None) -> float:
        stmt = select(func.coalesce(func.sum(SubscriptionBill.amount), 0)).where(
            SubscriptionBill.deleted_at.is_(None)
        )
        if status is not None:
            stmt = stmt.where(SubscriptionBill.status == status)
        return _sum(db, stmt)

    return {
        # Legacy / Phase 1–2 keys
        "schools": schools_total,
        "schools_active": schools_active,
        "packages": packages_total,
        "packages_active": packages_active,
        "super_admins": super_admins,
        # Phase 7 expansions
        "schools_inactive": schools_inactive,
        "schools_deactivated": schools_deactivated,
        "students": students_total,
        "school_admins": school_admins,
        "v1_users": v1_users,
        "plans": packages_total,
        "plans_active": packages_active,
        "subscriptions": subscriptions_total,
        "subscriptions_active": sub_count(SUB_STATUS_ACTIVE),
        "subscriptions_inactive": sub_count(SUB_STATUS_INACTIVE),
        "subscriptions_expired": sub_count(SUB_STATUS_EXPIRED),
        "subscriptions_cancelled": sub_count(SUB_STATUS_CANCELLED),
        "addons": addons_total,
        "addons_active": addons_active,
        "addon_assignments_active": addon_assignments_active,
        "bills": _count(
            db,
            select(func.count())
            .select_from(SubscriptionBill)
            .where(SubscriptionBill.deleted_at.is_(None)),
        ),
        "bills_pending": bill_count(BILL_STATUS_PENDING),
        "bills_paid": bill_count(BILL_STATUS_PAID),
        "bills_overdue": bill_count(BILL_STATUS_OVERDUE),
        "bills_cancelled": bill_count(BILL_STATUS_CANCELLED),
        # Bill amounts from subscription_bills only — NOT gateway-collected revenue.
        "bill_amount_total": bill_amount(),
        "bill_amount_pending": bill_amount(BILL_STATUS_PENDING),
        "bill_amount_paid": bill_amount(BILL_STATUS_PAID),
        "unavailable_metrics": [
            "payment_gateway_revenue",
            "payment_transactions",
        ],
    }
