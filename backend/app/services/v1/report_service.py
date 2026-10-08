"""Super Admin filterable reports (Phase 7) — read-only over existing tables."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import Package, School, Subscription, SubscriptionBill


class ReportServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def report_schools(
    db: Session,
    *,
    status: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = select(School).where(School.deleted_at.is_(None))
    count_query = select(func.count()).select_from(School).where(School.deleted_at.is_(None))
    if status is not None:
        query = query.where(School.status == status)
        count_query = count_query.where(School.status == status)
    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(query.order_by(School.id.desc()).offset((page - 1) * page_size).limit(page_size))
    )
    items = [
        {
            "id": s.id,
            "name": s.name,
            "code": s.code,
            "status": s.status,
            "installed": s.installed,
            "created_at": s.created_at,
        }
        for s in rows
    ]
    return items, total


def report_subscriptions(
    db: Session,
    *,
    status: int | None = None,
    package_id: int | None = None,
    school_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    if start_date and end_date and end_date < start_date:
        raise ReportServiceError("end_date must be on or after start_date", status_code=422)
    if package_id is not None:
        pkg = db.get(Package, package_id)
        if pkg is None or pkg.deleted_at is not None:
            raise ReportServiceError("Plan not found", status_code=404)
    if school_id is not None:
        school = db.get(School, school_id)
        if school is None or school.deleted_at is not None:
            raise ReportServiceError("School not found", status_code=404)

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = select(Subscription).where(Subscription.deleted_at.is_(None))
    count_query = (
        select(func.count()).select_from(Subscription).where(Subscription.deleted_at.is_(None))
    )
    if status is not None:
        query = query.where(Subscription.status == status)
        count_query = count_query.where(Subscription.status == status)
    if package_id is not None:
        query = query.where(Subscription.package_id == package_id)
        count_query = count_query.where(Subscription.package_id == package_id)
    if school_id is not None:
        query = query.where(Subscription.school_id == school_id)
        count_query = count_query.where(Subscription.school_id == school_id)
    if start_date is not None:
        query = query.where(Subscription.start_date >= start_date)
        count_query = count_query.where(Subscription.start_date >= start_date)
    if end_date is not None:
        query = query.where(Subscription.end_date <= end_date)
        count_query = count_query.where(Subscription.end_date <= end_date)

    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(
            query.order_by(Subscription.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    )
    items = [
        {
            "id": s.id,
            "school_id": s.school_id,
            "package_id": s.package_id,
            "status": s.status,
            "start_date": s.start_date,
            "end_date": s.end_date,
            "cycle": s.cycle,
        }
        for s in rows
    ]
    return items, total


def report_bills(
    db: Session,
    *,
    status: int | None = None,
    school_id: int | None = None,
    subscription_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], float, int]:
    """Returns (items, amount_sum_for_filters, total_count)."""
    if start_date and end_date and end_date < start_date:
        raise ReportServiceError("end_date must be on or after start_date", status_code=422)
    if school_id is not None:
        school = db.get(School, school_id)
        if school is None or school.deleted_at is not None:
            raise ReportServiceError("School not found", status_code=404)

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    base = SubscriptionBill.deleted_at.is_(None)
    query = select(SubscriptionBill).where(base)
    count_query = select(func.count()).select_from(SubscriptionBill).where(base)
    sum_query = select(func.coalesce(func.sum(SubscriptionBill.amount), 0)).where(base)

    if status is not None:
        query = query.where(SubscriptionBill.status == status)
        count_query = count_query.where(SubscriptionBill.status == status)
        sum_query = sum_query.where(SubscriptionBill.status == status)
    if school_id is not None:
        query = query.where(SubscriptionBill.school_id == school_id)
        count_query = count_query.where(SubscriptionBill.school_id == school_id)
        sum_query = sum_query.where(SubscriptionBill.school_id == school_id)
    if subscription_id is not None:
        query = query.where(SubscriptionBill.subscription_id == subscription_id)
        count_query = count_query.where(SubscriptionBill.subscription_id == subscription_id)
        sum_query = sum_query.where(SubscriptionBill.subscription_id == subscription_id)
    if start_date is not None:
        query = query.where(SubscriptionBill.period_start >= start_date)
        count_query = count_query.where(SubscriptionBill.period_start >= start_date)
        sum_query = sum_query.where(SubscriptionBill.period_start >= start_date)
    if end_date is not None:
        query = query.where(SubscriptionBill.period_end <= end_date)
        count_query = count_query.where(SubscriptionBill.period_end <= end_date)
        sum_query = sum_query.where(SubscriptionBill.period_end <= end_date)

    total = int(db.scalar(count_query) or 0)
    amount_sum = float(db.scalar(sum_query) or 0)
    rows = list(
        db.scalars(
            query.order_by(SubscriptionBill.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    items = [
        {
            "id": b.id,
            "subscription_id": b.subscription_id,
            "school_id": b.school_id,
            "amount": float(b.amount),
            "status": b.status,
            "period_start": b.period_start,
            "period_end": b.period_end,
            "due_date": b.due_date,
        }
        for b in rows
    ]
    return items, amount_sum, total
