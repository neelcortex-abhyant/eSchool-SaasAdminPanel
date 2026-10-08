"""Super Admin school subscriptions + bills (Phase 5). No payment gateways."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import Package, School, Subscription, SubscriptionBill

# Subscription lifecycle
SUB_STATUS_INACTIVE = 0
SUB_STATUS_ACTIVE = 1
SUB_STATUS_EXPIRED = 2
SUB_STATUS_CANCELLED = 3
SUB_STATUSES = frozenset(
    {SUB_STATUS_INACTIVE, SUB_STATUS_ACTIVE, SUB_STATUS_EXPIRED, SUB_STATUS_CANCELLED}
)

# Bill lifecycle (collection/payment is a later phase)
BILL_STATUS_PENDING = 0
BILL_STATUS_PAID = 1
BILL_STATUS_OVERDUE = 2
BILL_STATUS_CANCELLED = 3
BILL_STATUSES = frozenset(
    {BILL_STATUS_PENDING, BILL_STATUS_PAID, BILL_STATUS_OVERDUE, BILL_STATUS_CANCELLED}
)

CYCLES = frozenset({"monthly", "yearly"})


class SubscriptionServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_school(db: Session, school_id: int) -> School:
    school = db.get(School, school_id)
    if school is None or school.deleted_at is not None:
        raise SubscriptionServiceError("School not found", status_code=404)
    return school


def _get_package(db: Session, package_id: int) -> Package:
    package = db.get(Package, package_id)
    if package is None or package.deleted_at is not None:
        raise SubscriptionServiceError("Plan not found", status_code=404)
    return package


def _validate_dates(start: date, end: date) -> None:
    if end < start:
        raise SubscriptionServiceError("end_date must be on or after start_date", status_code=422)


def _deactivate_active_for_school(db: Session, school_id: int, *, except_id: int | None = None) -> None:
    """Terminate other active subscriptions when a new active one is assigned."""
    query = select(Subscription).where(
        Subscription.school_id == school_id,
        Subscription.status == SUB_STATUS_ACTIVE,
        Subscription.deleted_at.is_(None),
    )
    if except_id is not None:
        query = query.where(Subscription.id != except_id)
    now = _utcnow()
    for row in db.scalars(query):
        row.status = SUB_STATUS_CANCELLED
        row.updated_at = now


def get_subscription(
    db: Session,
    school_id: int,
    subscription_id: int,
    *,
    include_deleted: bool = False,
) -> Subscription:
    _get_school(db, school_id)
    sub = db.get(Subscription, subscription_id)
    if (
        sub is None
        or sub.school_id != school_id
        or (not include_deleted and sub.deleted_at is not None)
    ):
        raise SubscriptionServiceError("Subscription not found", status_code=404)
    return sub


def create_subscription(
    db: Session,
    school_id: int,
    *,
    package_id: int,
    start_date: date,
    end_date: date,
    cycle: str = "monthly",
    auto_renew: int = 1,
    status: int = SUB_STATUS_ACTIVE,
) -> Subscription:
    _get_school(db, school_id)
    _get_package(db, package_id)
    if cycle not in CYCLES:
        raise SubscriptionServiceError("cycle must be monthly or yearly", status_code=422)
    if status not in SUB_STATUSES:
        raise SubscriptionServiceError("Invalid subscription status", status_code=422)
    if auto_renew not in (0, 1):
        raise SubscriptionServiceError("auto_renew must be 0 or 1", status_code=422)
    _validate_dates(start_date, end_date)

    if status == SUB_STATUS_ACTIVE:
        _deactivate_active_for_school(db, school_id)

    now = _utcnow()
    sub = Subscription(
        school_id=school_id,
        package_id=package_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        cycle=cycle,
        auto_renew=auto_renew,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def list_subscriptions(
    db: Session,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
) -> tuple[list[Subscription], int]:
    _get_school(db, school_id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = select(Subscription).where(
        Subscription.school_id == school_id,
        Subscription.deleted_at.is_(None),
    )
    count_query = (
        select(func.count())
        .select_from(Subscription)
        .where(Subscription.school_id == school_id, Subscription.deleted_at.is_(None))
    )
    if status is not None:
        query = query.where(Subscription.status == status)
        count_query = count_query.where(Subscription.status == status)

    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(
            query.order_by(Subscription.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    )
    return rows, total


def update_subscription(
    db: Session,
    school_id: int,
    subscription_id: int,
    *,
    package_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    cycle: str | None = None,
    auto_renew: int | None = None,
) -> Subscription:
    sub = get_subscription(db, school_id, subscription_id)
    if package_id is not None:
        _get_package(db, package_id)
        sub.package_id = package_id
    if cycle is not None:
        if cycle not in CYCLES:
            raise SubscriptionServiceError("cycle must be monthly or yearly", status_code=422)
        sub.cycle = cycle
    if auto_renew is not None:
        if auto_renew not in (0, 1):
            raise SubscriptionServiceError("auto_renew must be 0 or 1", status_code=422)
        sub.auto_renew = auto_renew
    new_start = start_date if start_date is not None else sub.start_date
    new_end = end_date if end_date is not None else sub.end_date
    _validate_dates(new_start, new_end)
    if start_date is not None:
        sub.start_date = start_date
    if end_date is not None:
        sub.end_date = end_date
    # Never allow school_id change via update.
    sub.updated_at = _utcnow()
    db.commit()
    db.refresh(sub)
    return sub


def set_subscription_status(
    db: Session,
    school_id: int,
    subscription_id: int,
    *,
    status: int,
) -> Subscription:
    if status not in SUB_STATUSES:
        raise SubscriptionServiceError("Invalid subscription status", status_code=422)
    sub = get_subscription(db, school_id, subscription_id)
    if status == SUB_STATUS_ACTIVE:
        _deactivate_active_for_school(db, school_id, except_id=sub.id)
    sub.status = status
    sub.updated_at = _utcnow()
    db.commit()
    db.refresh(sub)
    return sub


def _default_bill_amount(package: Package, cycle: str) -> float:
    if cycle == "yearly":
        return float(package.yearly_price or 0)
    return float(package.monthly_price or 0)


def create_bill(
    db: Session,
    school_id: int,
    subscription_id: int,
    *,
    period_start: date,
    period_end: date,
    amount: float | None = None,
    due_date: date | None = None,
    description: str | None = None,
    status: int = BILL_STATUS_PENDING,
) -> SubscriptionBill:
    sub = get_subscription(db, school_id, subscription_id)
    if status not in BILL_STATUSES:
        raise SubscriptionServiceError("Invalid bill status", status_code=422)
    _validate_dates(period_start, period_end)
    package = _get_package(db, sub.package_id)
    resolved_amount = float(amount) if amount is not None else _default_bill_amount(package, sub.cycle)
    if resolved_amount < 0:
        raise SubscriptionServiceError("amount must be >= 0", status_code=422)

    now = _utcnow()
    bill = SubscriptionBill(
        subscription_id=sub.id,
        school_id=school_id,
        amount=resolved_amount,
        status=status,
        period_start=period_start,
        period_end=period_end,
        due_date=due_date,
        description=(description[:255] if description else None),
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill


def list_bills(
    db: Session,
    school_id: int,
    subscription_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
) -> tuple[list[SubscriptionBill], int]:
    get_subscription(db, school_id, subscription_id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = select(SubscriptionBill).where(
        SubscriptionBill.subscription_id == subscription_id,
        SubscriptionBill.school_id == school_id,
        SubscriptionBill.deleted_at.is_(None),
    )
    count_query = (
        select(func.count())
        .select_from(SubscriptionBill)
        .where(
            SubscriptionBill.subscription_id == subscription_id,
            SubscriptionBill.school_id == school_id,
            SubscriptionBill.deleted_at.is_(None),
        )
    )
    if status is not None:
        query = query.where(SubscriptionBill.status == status)
        count_query = count_query.where(SubscriptionBill.status == status)

    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(
            query.order_by(SubscriptionBill.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def get_bill(
    db: Session,
    school_id: int,
    subscription_id: int,
    bill_id: int,
) -> SubscriptionBill:
    get_subscription(db, school_id, subscription_id)
    bill = db.get(SubscriptionBill, bill_id)
    if (
        bill is None
        or bill.deleted_at is not None
        or bill.subscription_id != subscription_id
        or bill.school_id != school_id
    ):
        raise SubscriptionServiceError("Subscription bill not found", status_code=404)
    return bill


def set_bill_status(
    db: Session,
    school_id: int,
    subscription_id: int,
    bill_id: int,
    *,
    status: int,
) -> SubscriptionBill:
    if status not in BILL_STATUSES:
        raise SubscriptionServiceError("Invalid bill status", status_code=422)
    bill = get_bill(db, school_id, subscription_id, bill_id)
    bill.status = status
    bill.updated_at = _utcnow()
    db.commit()
    db.refresh(bill)
    return bill
