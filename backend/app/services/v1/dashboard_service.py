"""Super Admin platform dashboard — DB-backed SaaS metrics (Phase 7)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.tables import (
    USER_MODEL,
    Addon,
    AddonSubscription,
    AuditLog,
    ModelHasRole,
    Package,
    Role,
    School,
    Student,
    Subscription,
    SubscriptionBill,
    User as LegacyUser,
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


def dashboard_stats(db: Session) -> dict:
    """Aggregate platform stats. One query per metric group.

    Schools: non-deleted rows. Active is status=1, inactive is status=0.
    Students: non-deleted student rows whose school is also non-deleted.
    Teachers: legacy users with role name Teacher, linked by users.school_id
    to a non-deleted school. Soft-deleted users are excluded.
    Active subscriptions: status=1 and deleted_at IS NULL, matching the
    existing dashboard subscription count.
    """
    school_counts = db.execute(
        select(
            func.count().filter(School.deleted_at.is_(None)),
            func.count().filter(School.deleted_at.is_(None), School.status == 1),
            func.count().filter(School.deleted_at.is_(None), School.status == 0),
        ).select_from(School)
    ).one()
    students = _count(
        db,
        select(func.count())
        .select_from(Student)
        .join(School, School.id == Student.school_id)
        .where(Student.deleted_at.is_(None), School.deleted_at.is_(None)),
    )
    teachers = _count(
        db,
        select(func.count(func.distinct(LegacyUser.id)))
        .select_from(LegacyUser)
        .join(School, School.id == LegacyUser.school_id)
        .join(ModelHasRole, ModelHasRole.model_id == LegacyUser.id)
        .join(Role, Role.id == ModelHasRole.role_id)
        .where(
            ModelHasRole.model_type == USER_MODEL,
            Role.name == "Teacher",
            LegacyUser.deleted_at.is_(None),
            School.deleted_at.is_(None),
        ),
    )
    active_subscriptions = _count(
        db,
        select(func.count())
        .select_from(Subscription)
        .where(
            Subscription.deleted_at.is_(None),
            Subscription.status == SUB_STATUS_ACTIVE,
        ),
    )
    return {
        "total_schools": int(school_counts[0] or 0),
        "active_schools": int(school_counts[1] or 0),
        "inactive_schools": int(school_counts[2] or 0),
        "total_students": students,
        "total_teachers": teachers,
        "active_subscriptions": active_subscriptions,
    }


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


def recent_schools(db: Session, *, limit: int) -> dict:
    """Newest non-deleted schools, with a plan only when exactly one is active.

    Plan fields come from one grouped subscription query for the returned
    school ids. A qualifying subscription has status=1 and deleted_at IS NULL.
    """
    schools = list(
        db.scalars(
            select(School)
            .where(School.deleted_at.is_(None))
            .order_by(School.created_at.desc().nulls_last(), School.id.desc())
            .limit(limit)
        )
    )
    plans: dict[int, tuple[int, str | None]] = {}
    school_ids = [school.id for school in schools]
    if school_ids:
        rows = db.execute(
            select(
                Subscription.school_id,
                func.count(Subscription.id),
                func.min(Subscription.package_id),
                func.min(Package.name),
            )
            .select_from(Subscription)
            .outerjoin(Package, Package.id == Subscription.package_id)
            .where(
                Subscription.school_id.in_(school_ids),
                Subscription.deleted_at.is_(None),
                Subscription.status == SUB_STATUS_ACTIVE,
            )
            .group_by(Subscription.school_id)
        ).all()
        for school_id, subscription_count, package_id, plan_name in rows:
            if int(subscription_count) == 1 and package_id is not None:
                plans[int(school_id)] = (int(package_id), plan_name)
    items = []
    for school in schools:
        package_id, plan_name = plans.get(school.id, (None, None))
        items.append(
            {
                "id": school.id,
                "name": school.name,
                "code": school.code,
                "created_at": school.created_at,
                "status": school.status,
                "installed": school.installed,
                "package_id": package_id,
                "plan_name": plan_name,
            }
        )
    return {"items": items, "limit": limit}


def registration_analytics(db: Session, *, year: int) -> dict:
    """Monthly school registrations for one naive-UTC calendar year.

    The window is [year-01-01, next-year-01-01). Null created_at rows are
    counted as unscheduled and are not included in total.
    """
    start = datetime(year, 1, 1)
    end = datetime(year + 1, 1, 1)
    month_expr = func.extract("month", School.created_at)
    rows = db.execute(
        select(month_expr, func.count())
        .select_from(School)
        .where(
            School.deleted_at.is_(None),
            or_(
                School.created_at.is_(None),
                and_(School.created_at >= start, School.created_at < end),
            ),
        )
        .group_by(month_expr)
    ).all()
    counts: dict[int, int] = {}
    unscheduled = 0
    for month, count in rows:
        if month is None:
            unscheduled = int(count)
        else:
            counts[int(month)] = int(count)
    months = [{"month": month, "count": counts.get(month, 0)} for month in range(1, 13)]
    return {
        "year": year,
        "total": sum(item["count"] for item in months),
        "unscheduled": unscheduled,
        "months": months,
    }


def school_status_distribution(db: Session) -> dict:
    """Active and inactive non-deleted schools. Same rules as dashboard stats."""
    row = db.execute(
        select(
            func.count().filter(School.deleted_at.is_(None), School.status == 1),
            func.count().filter(School.deleted_at.is_(None), School.status == 0),
        ).select_from(School)
    ).one()
    return {
        "active_schools": int(row[0] or 0),
        "inactive_schools": int(row[1] or 0),
    }


def subscription_distribution(db: Session) -> dict:
    """Distinct non-deleted schools per plan for qualifying active subscriptions.

    A qualifying row has status=1 and deleted_at IS NULL. end_date is not applied.
    Subscriptions on soft-deleted schools are excluded. Duplicate rows for the
    same school and plan count once. Stats still counts those rows individually.
    """
    qualifying = (
        Subscription.status == SUB_STATUS_ACTIVE,
        Subscription.deleted_at.is_(None),
        School.deleted_at.is_(None),
    )
    plan_rows = db.execute(
        select(
            Subscription.package_id,
            Package.name,
            func.count(func.distinct(Subscription.school_id)),
        )
        .select_from(Subscription)
        .join(School, School.id == Subscription.school_id)
        .outerjoin(Package, Package.id == Subscription.package_id)
        .where(*qualifying)
        .group_by(Subscription.package_id, Package.name)
        .order_by(Subscription.package_id.asc())
    ).all()
    schools_with = _count(
        db,
        select(func.count(func.distinct(Subscription.school_id)))
        .select_from(Subscription)
        .join(School, School.id == Subscription.school_id)
        .where(*qualifying),
    )
    schools_total = _count(
        db, select(func.count()).select_from(School).where(School.deleted_at.is_(None))
    )
    return {
        "by_plan": [
            {
                "package_id": int(package_id),
                "plan_name": plan_name,
                "school_count": int(school_count),
            }
            for package_id, plan_name, school_count in plan_rows
        ],
        "schools_with_active_subscription": schools_with,
        "schools_without_active_subscription": schools_total - schools_with,
    }


_ACTIVITY_COPY: dict[str, tuple[str, str]] = {
    "school.register": ("New school registration", "A school registered and is waiting for approval."),
    "school.create": ("School created", "A school was created."),
    "school.update": ("School updated", "A school's details were updated."),
    "school.delete": ("School deleted", "A school was deleted."),
    "school.activate": ("School activation", "A school was activated."),
    "school.suspend": ("School suspended", "A school was suspended."),
    "school.deactivate": ("School deactivation", "A school was deactivated."),
    "school.provision": ("School provisioned", "A school was provisioned."),
    "school_admin.create": ("School admin created", "A school administrator was created."),
    "school_admin.update": ("School admin updated", "A school administrator was updated."),
    "school_admin.status": ("School admin status changed", "A school administrator's status was changed."),
    "school_admin.roles": ("School admin roles changed", "A school administrator's roles were changed."),
    "subscription.create": ("Subscription creation", "A subscription was created."),
    "subscription.update": ("Subscription updated", "A subscription was updated."),
    "subscription.renew": ("Subscription renewed", "A subscription was renewed."),
    "subscription.expire": ("Subscriptions expired", "Due subscriptions were marked expired."),
    "subscription.status": ("Subscription status changed", "A subscription's status was changed."),
    "bill.status": ("Bill status changed", "A subscription bill's status was changed."),
    "plan.create": ("Plan created", "A plan was created."),
    "plan.update": ("Plan updated", "A plan was updated."),
    "plan.status": ("Plan status changed", "A plan's status was changed."),
    "addon.create": ("Add-on created", "An add-on was created."),
    "addon.update": ("Add-on updated", "An add-on was updated."),
    "addon.status": ("Add-on status changed", "An add-on's status was changed."),
    "addon.assign": ("Add-on assigned", "An add-on was assigned to a school."),
    "addon.assignment_status": ("Add-on assignment updated", "An add-on assignment status was changed."),
    "notification.create": ("Notification created", "A notification was created."),
    "notification.status": ("Notification status changed", "A notification's status was changed."),
    "settings.update": ("Settings updated", "Platform settings were updated."),
}
_UNKNOWN_ACTIVITY = ("Activity recorded", "An activity was recorded.")


def recent_activities(db: Session, *, limit: int) -> dict:
    """Newest audit rows by id, matching the audit-log list order.

    Titles are derived from the stored action. subscription.renew is
    "Subscription renewed". A renewal is shown only when that audit row exists.
    """
    rows = db.execute(
        select(
            AuditLog.id,
            AuditLog.action,
            AuditLog.entity_type,
            AuditLog.entity_id,
            AuditLog.school_id,
            AuditLog.created_at,
        )
        .order_by(AuditLog.id.desc())
        .limit(limit)
    ).all()
    items = []
    for row in rows:
        title, description = _ACTIVITY_COPY.get(row.action, _UNKNOWN_ACTIVITY)
        items.append(
            {
                "id": row.id,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "school_id": row.school_id,
                "created_at": row.created_at,
                "title": title,
                "description": description,
            }
        )
    return {"items": items}
