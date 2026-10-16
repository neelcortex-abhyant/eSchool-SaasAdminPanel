"""Super Admin school subscriptions, bills, and renewals. No payment gateways."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.tables import Package, School, Subscription, SubscriptionBill, SubscriptionRenewal
from app.services.v1.plan_service import (
    STATUS_ACTIVE as PLAN_STATUS_ACTIVE,
    normalize_money,
)

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


def _save(db: Session, row, *, commit: bool):
    """Commit, or flush so the caller can commit this change with its audit record.

    A refresh failure after a successful commit does not undo that commit.
    """
    if not commit:
        try:
            db.flush()
        except Exception:
            db.rollback()
            raise
        return row
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    try:
        db.refresh(row)
    except Exception:
        return row
    return row


def utc_today() -> date:
    """Calendar date for renewal rules. Naive UTC, same clock as stored timestamps."""
    return _utcnow().date()


def add_calendar_months(value: date, months: int) -> date:
    """Add calendar months, clamping the day to the last valid day of the target month."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def add_calendar_years(value: date, years: int) -> date:
    """Add calendar years. February 29 becomes February 28 in a non-leap year."""
    year = value.year + years
    day = min(value.day, monthrange(year, value.month)[1])
    return date(year, value.month, day)


def renewed_period(end_date: date, cycle: str, *, today: date) -> tuple[date, date]:
    """Return the inclusive renewed period for a stored cycle.

    If ``end_date`` is today or later, the new period starts the next day.
    If ``end_date`` is already past, the new period starts on ``today``.
    Monthly adds one calendar month. Yearly adds one calendar year.
    The returned end date is included in the period.
    """
    if cycle not in CYCLES:
        raise SubscriptionServiceError("cycle must be monthly or yearly", status_code=422)
    start = end_date + timedelta(days=1) if end_date >= today else today
    if cycle == "yearly":
        end = add_calendar_years(start, 1)
    else:
        end = add_calendar_months(start, 1)
    return start, end


def _get_school(db: Session, school_id: int) -> School:
    school = db.get(School, school_id)
    if school is None or school.deleted_at is not None:
        raise SubscriptionServiceError("School not found", status_code=404)
    return school


def _lock_school(db: Session, school_id: int) -> School:
    """Hold the school row so two activations cannot both remain active.

    The lock is taken before other active rows are cancelled. It does not
    remove active rows that were already stored, and it is not a unique index.
    """
    school = db.scalar(select(School).where(School.id == school_id).with_for_update())
    if school is None or school.deleted_at is not None:
        raise SubscriptionServiceError("School not found", status_code=404)
    return school


def _get_package(db: Session, package_id: int) -> Package:
    package = db.get(Package, package_id)
    if package is None or package.deleted_at is not None:
        raise SubscriptionServiceError("Plan not found", status_code=404)
    return package


def _require_active_plan(package: Package) -> None:
    if package.status != PLAN_STATUS_ACTIVE:
        raise SubscriptionServiceError("Plan is not active", status_code=422)


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
    commit: bool = True,
) -> Subscription:
    _get_school(db, school_id)
    package = _get_package(db, package_id)
    _require_active_plan(package)
    if cycle not in CYCLES:
        raise SubscriptionServiceError("cycle must be monthly or yearly", status_code=422)
    if status not in SUB_STATUSES:
        raise SubscriptionServiceError("Invalid subscription status", status_code=422)
    if auto_renew not in (0, 1):
        raise SubscriptionServiceError("auto_renew must be 0 or 1", status_code=422)
    _validate_dates(start_date, end_date)
    agreed_price = _cycle_amount(package, cycle)

    if status == SUB_STATUS_ACTIVE:
        _lock_school(db, school_id)
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
        agreed_price=agreed_price,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(sub)
    return _save(db, sub, commit=commit)


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


_PLATFORM_SORTS = {
    "end_date": (Subscription.end_date.asc().nulls_last(), Subscription.id.asc()),
    "-end_date": (Subscription.end_date.desc().nulls_last(), Subscription.id.desc()),
    "created_at": (Subscription.created_at.asc().nulls_last(), Subscription.id.asc()),
    "-created_at": (Subscription.created_at.desc().nulls_last(), Subscription.id.desc()),
}


def list_platform_subscriptions(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    status: int | None = None,
    package_id: int | None = None,
    school_id: int | None = None,
    sort: str | None = None,
) -> tuple[list[tuple[Subscription, str, str | None]], int]:
    """List subscriptions across schools. Read-only: no status or audit writes.

    Soft-deleted subscriptions and subscriptions on soft-deleted schools are omitted.
    Soft-deleted plans are still listed. end_date is required. created_at may be null
    and sorts last in both directions. The default sort is end_date ascending, then id.
    """
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    sort_key = (sort or "end_date").strip() or "end_date"
    if sort_key not in _PLATFORM_SORTS:
        raise SubscriptionServiceError("Invalid sort", status_code=422)
    if status is not None and status not in SUB_STATUSES:
        raise SubscriptionServiceError("Invalid status", status_code=422)

    conditions = [
        Subscription.deleted_at.is_(None),
        School.deleted_at.is_(None),
    ]
    if status is not None:
        conditions.append(Subscription.status == status)
    if package_id is not None:
        conditions.append(Subscription.package_id == package_id)
    if school_id is not None:
        conditions.append(Subscription.school_id == school_id)
    if q and q.strip():
        conditions.append(School.name.ilike(f"%{q.strip()}%"))

    joined_from = (
        select(Subscription, School.name, Package.name)
        .join(School, School.id == Subscription.school_id)
        .join(Package, Package.id == Subscription.package_id)
        .where(*conditions)
    )
    total = int(
        db.scalar(
            select(func.count())
            .select_from(Subscription)
            .join(School, School.id == Subscription.school_id)
            .join(Package, Package.id == Subscription.package_id)
            .where(*conditions)
        )
        or 0
    )
    rows = [
        (row[0], row[1], row[2])
        for row in db.execute(
            joined_from.order_by(*_PLATFORM_SORTS[sort_key])
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    ]
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
    commit: bool = True,
) -> Subscription:
    sub = get_subscription(db, school_id, subscription_id)
    rebind_price = package_id is not None or cycle is not None
    next_package_id = package_id if package_id is not None else sub.package_id
    next_cycle = cycle if cycle is not None else sub.cycle
    agreed_price = None
    if rebind_price:
        if next_cycle not in CYCLES:
            raise SubscriptionServiceError("cycle must be monthly or yearly", status_code=422)
        agreed_price = _cycle_amount(_get_package(db, next_package_id), next_cycle)
    if package_id is not None:
        sub.package_id = package_id
    if cycle is not None:
        sub.cycle = cycle
    if rebind_price:
        sub.agreed_price = agreed_price
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
    return _save(db, sub, commit=commit)


def set_subscription_status(
    db: Session,
    school_id: int,
    subscription_id: int,
    *,
    status: int,
    commit: bool = True,
) -> Subscription:
    if status not in SUB_STATUSES:
        raise SubscriptionServiceError("Invalid subscription status", status_code=422)
    sub = get_subscription(db, school_id, subscription_id)
    if status == SUB_STATUS_ACTIVE:
        _lock_school(db, school_id)
        _deactivate_active_for_school(db, school_id, except_id=sub.id)
    sub.status = status
    sub.updated_at = _utcnow()
    return _save(db, sub, commit=commit)


def _default_bill_amount(package: Package, cycle: str) -> float:
    return float(_cycle_amount(package, cycle))


def _cycle_amount(package: Package, cycle: str) -> Decimal:
    raw = package.yearly_price if cycle == "yearly" else package.monthly_price
    try:
        return normalize_money(float(raw or 0))
    except ValueError:
        raise SubscriptionServiceError(
            "Plan price exceeds the supported amount",
            status_code=422,
        ) from None


def _sqlstate(exc: DBAPIError) -> str | None:
    orig = getattr(exc, "orig", None)
    if orig is None:
        return None
    return getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)


def _is_lock_not_available(exc: DBAPIError) -> bool:
    return _sqlstate(exc) == "55P03"


def _is_renewal_period_conflict(exc: DBAPIError) -> bool:
    if _sqlstate(exc) != "23505":
        return False
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    name = getattr(diag, "constraint_name", None) if diag is not None else None
    return name in (None, "uq_subscription_renewals_period")


def renew_subscription(
    db: Session,
    school_id: int,
    subscription_id: int,
    *,
    today: date | None = None,
    commit: bool = True,
) -> Subscription:
    """Extend one active subscription and record an immutable renewal plus a pending bill.

    Accepted status is active (1) only. Inactive (0), expired (2), and cancelled (3)
    are rejected. A past end_date does not block renewal while status remains 1.
    The subscription row and its id are kept. No payment is collected.

    The subscription update, history insert, and pending bill are one transaction.
    Pass commit=False to leave that transaction open so the caller can write the
    audit row before the single commit. This function does not write an audit row.
    The subscription row is locked with FOR UPDATE NOWAIT. A concurrent renewal
    returns 409. The unique (subscription_id, period_start) constraint is the
    durable guard for the same period.
    """
    as_of = today if today is not None else utc_today()
    _get_school(db, school_id)
    try:
        sub = db.scalar(
            select(Subscription)
            .where(Subscription.id == subscription_id)
            .with_for_update(nowait=True)
        )
        if sub is None or sub.school_id != school_id or sub.deleted_at is not None:
            raise SubscriptionServiceError("Subscription not found", status_code=404)
        if sub.status != SUB_STATUS_ACTIVE:
            raise SubscriptionServiceError("Only an active subscription can be renewed", status_code=422)
        if sub.cycle not in CYCLES:
            raise SubscriptionServiceError("cycle must be monthly or yearly", status_code=422)
        package = _get_package(db, sub.package_id)
        _require_active_plan(package)

        period_start, period_end = renewed_period(sub.end_date, sub.cycle, today=as_of)
        amount = _cycle_amount(package, sub.cycle)
        now = _utcnow()
        sub.start_date = period_start
        sub.end_date = period_end
        sub.status = SUB_STATUS_ACTIVE
        sub.updated_at = now
        plan_name = (package.name or "")[:255]
        db.add(
            SubscriptionRenewal(
                subscription_id=sub.id,
                school_id=school_id,
                package_id=package.id,
                plan_name=plan_name,
                cycle=sub.cycle,
                amount=amount,
                period_start=period_start,
                period_end=period_end,
                created_at=now,
            )
        )
        db.add(
            SubscriptionBill(
                subscription_id=sub.id,
                school_id=school_id,
                amount=float(amount),
                status=BILL_STATUS_PENDING,
                period_start=period_start,
                period_end=period_end,
                due_date=None,
                description="Subscription renewal",
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        if commit:
            db.commit()
        else:
            db.flush()
    except SubscriptionServiceError:
        db.rollback()
        raise
    except DBAPIError as exc:
        db.rollback()
        if _is_lock_not_available(exc):
            raise SubscriptionServiceError(
                "A renewal for this subscription is already in progress",
                status_code=409,
            ) from exc
        if _is_renewal_period_conflict(exc):
            raise SubscriptionServiceError(
                "This subscription period has already been renewed",
                status_code=409,
            ) from exc
        raise
    except Exception:
        db.rollback()
        raise
    if commit:
        db.refresh(sub)
    return sub


def list_renewals(
    db: Session,
    school_id: int,
    subscription_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SubscriptionRenewal], int]:
    """List immutable renewal snapshots for one subscription.

    A missing school, a soft-deleted school, a missing subscription, a
    soft-deleted subscription, or a subscription for another school is 404.
    Renewal rows have no soft-delete flag. Order is id descending.
    """
    get_subscription(db, school_id, subscription_id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    where = (
        SubscriptionRenewal.subscription_id == subscription_id,
        SubscriptionRenewal.school_id == school_id,
    )
    total = int(
        db.scalar(select(func.count()).select_from(SubscriptionRenewal).where(*where)) or 0
    )
    rows = list(
        db.scalars(
            select(SubscriptionRenewal)
            .where(*where)
            .order_by(SubscriptionRenewal.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def expire_due_subscriptions(
    db: Session,
    *,
    today: date | None = None,
    commit: bool = True,
) -> int:
    """Set status to expired for active subscriptions whose end date is before today.

    Today is the naive UTC calendar date. An end date equal to today stays active.
    Statuses other than active, and soft-deleted rows, are left unchanged.
    School status and installed are not read or written. Returns how many rows
    changed. Pass commit=False to keep the update in the caller's transaction.
    """
    as_of = today if today is not None else utc_today()
    try:
        result = db.execute(
            update(Subscription)
            .where(
                Subscription.status == SUB_STATUS_ACTIVE,
                Subscription.deleted_at.is_(None),
                Subscription.end_date < as_of,
            )
            .values(status=SUB_STATUS_EXPIRED, updated_at=_utcnow())
            .returning(Subscription.id)
        )
        count = len(result.all())
        if commit:
            db.commit()
        return count
    except Exception:
        db.rollback()
        raise


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
    if amount is not None:
        try:
            resolved_amount = float(normalize_money(amount))
        except ValueError:
            raise SubscriptionServiceError(
                "amount must be from 0 through 9999999999.99",
                status_code=422,
            ) from None
    else:
        resolved_amount = _default_bill_amount(package, sub.cycle)

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
    commit: bool = True,
) -> SubscriptionBill:
    if status not in BILL_STATUSES:
        raise SubscriptionServiceError("Invalid bill status", status_code=422)
    bill = get_bill(db, school_id, subscription_id, bill_id)
    bill.status = status
    bill.updated_at = _utcnow()
    return _save(db, bill, commit=commit)
