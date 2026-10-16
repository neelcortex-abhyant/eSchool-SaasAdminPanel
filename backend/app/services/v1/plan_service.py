"""Super Admin plans — reuses legacy Package model (table `packages`)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import Package

STATUS_INACTIVE = 0
STATUS_ACTIVE = 1

# Largest value that fits in subscription_renewals.amount numeric(12,2).
MAX_PLAN_PRICE = Decimal("9999999999.99")


class PlanServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise PlanServiceError("Plan name is required", status_code=422)
    return cleaned[:255]


def _ensure_name_available(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    query = select(Package.id).where(
        Package.name == name,
        Package.deleted_at.is_(None),
    )
    if exclude_id is not None:
        query = query.where(Package.id != exclude_id)
    if db.scalar(query) is not None:
        raise PlanServiceError("Plan name already in use", status_code=409)


def quantized_plan_price(value: float) -> Decimal:
    """Round a plan price to cents, matching the renewal snapshot."""
    return Decimal(str(value if value is not None else 0)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def normalize_money(value: float) -> Decimal:
    """Round to cents. Reject negatives, negative zero, and values above the maximum.

    ``-0.001`` quantizes to ``-0.00``. That result is not less than zero, so the
    sign of the raw value and of the rounded result are both checked.
    """
    raw = 0.0 if value is None else float(value)
    if raw < 0:
        raise ValueError("must be from 0 through 9999999999.99")
    amount = quantized_plan_price(raw)
    if amount.is_signed() or amount > MAX_PLAN_PRICE:
        raise ValueError("must be from 0 through 9999999999.99")
    return amount


def _validated_price(value: float) -> float:
    try:
        return float(normalize_money(value))
    except ValueError:
        raise PlanServiceError(
            "monthly_price and yearly_price must be from 0 through 9999999999.99",
            status_code=422,
        ) from None


def _validate_limits(student_limit: int | None, staff_limit: int | None) -> None:
    if student_limit is not None and student_limit < 0:
        raise PlanServiceError("student_limit must be >= 0", status_code=422)
    if staff_limit is not None and staff_limit < 0:
        raise PlanServiceError("staff_limit must be >= 0", status_code=422)


def _save(db: Session, row: Package, *, commit: bool) -> Package:
    """Commit, or flush so the caller can commit this row with its audit record."""
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


def get_plan(db: Session, plan_id: int, *, include_deleted: bool = False) -> Package:
    plan = db.get(Package, plan_id)
    if plan is None or (not include_deleted and plan.deleted_at is not None):
        raise PlanServiceError("Plan not found", status_code=404)
    return plan


def create_plan(
    db: Session,
    *,
    name: str,
    description: str = "",
    monthly_price: float = 0.0,
    yearly_price: float = 0.0,
    student_limit: int | None = None,
    staff_limit: int | None = None,
    commit: bool = True,
) -> Package:
    normalized = _normalize_name(name)
    _ensure_name_available(db, normalized)
    monthly = _validated_price(monthly_price)
    yearly = _validated_price(yearly_price)
    _validate_limits(student_limit, staff_limit)
    now = _utcnow()
    plan = Package(
        name=normalized,
        description=(description or "")[:255],
        status=STATUS_INACTIVE,  # unpublished until Super Admin activates
        monthly_price=monthly,
        yearly_price=yearly,
        student_limit=student_limit,
        staff_limit=staff_limit,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(plan)
    return _save(db, plan, commit=commit)


def list_plans(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
    name: str | None = None,
    include_deleted: bool = False,
) -> tuple[list[Package], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = select(Package)
    count_query = select(func.count()).select_from(Package)

    if not include_deleted:
        query = query.where(Package.deleted_at.is_(None))
        count_query = count_query.where(Package.deleted_at.is_(None))
    if status is not None:
        query = query.where(Package.status == status)
        count_query = count_query.where(Package.status == status)
    if name:
        like = f"%{name.strip()}%"
        query = query.where(Package.name.ilike(like))
        count_query = count_query.where(Package.name.ilike(like))

    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(query.order_by(Package.id.desc()).offset((page - 1) * page_size).limit(page_size))
    )
    return rows, total


def update_plan(
    db: Session,
    plan_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    monthly_price: float | None = None,
    yearly_price: float | None = None,
    student_limit: int | None = None,
    student_limit_set: bool = False,
    staff_limit: int | None = None,
    staff_limit_set: bool = False,
    commit: bool = True,
) -> Package:
    plan = get_plan(db, plan_id)
    if name is not None:
        normalized = _normalize_name(name)
        _ensure_name_available(db, normalized, exclude_id=plan.id)
        plan.name = normalized
    if description is not None:
        plan.description = description[:255]
    if monthly_price is not None or yearly_price is not None:
        mp = (
            _validated_price(monthly_price)
            if monthly_price is not None
            else _validated_price(float(plan.monthly_price or 0))
        )
        yp = (
            _validated_price(yearly_price)
            if yearly_price is not None
            else _validated_price(float(plan.yearly_price or 0))
        )
        if monthly_price is not None:
            plan.monthly_price = mp
        if yearly_price is not None:
            plan.yearly_price = yp
    if student_limit_set:
        _validate_limits(student_limit, None)
        plan.student_limit = student_limit
    if staff_limit_set:
        _validate_limits(None, staff_limit)
        plan.staff_limit = staff_limit
    plan.updated_at = _utcnow()
    return _save(db, plan, commit=commit)


def set_plan_status(db: Session, plan_id: int, *, status: int, commit: bool = True) -> Package:
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise PlanServiceError("Invalid status", status_code=422)
    plan = get_plan(db, plan_id)
    plan.status = status
    plan.updated_at = _utcnow()
    return _save(db, plan, commit=commit)
