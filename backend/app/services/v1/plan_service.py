"""Super Admin plans — reuses legacy Package model (table `packages`)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import Package

STATUS_INACTIVE = 0
STATUS_ACTIVE = 1


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


def _validate_prices(monthly_price: float, yearly_price: float) -> None:
    if monthly_price < 0 or yearly_price < 0:
        raise PlanServiceError("Prices must be >= 0", status_code=422)


def _validate_limits(student_limit: int | None, staff_limit: int | None) -> None:
    if student_limit is not None and student_limit < 0:
        raise PlanServiceError("student_limit must be >= 0", status_code=422)
    if staff_limit is not None and staff_limit < 0:
        raise PlanServiceError("staff_limit must be >= 0", status_code=422)


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
) -> Package:
    normalized = _normalize_name(name)
    _ensure_name_available(db, normalized)
    _validate_prices(monthly_price, yearly_price)
    _validate_limits(student_limit, staff_limit)
    now = _utcnow()
    plan = Package(
        name=normalized,
        description=(description or "")[:255],
        status=STATUS_INACTIVE,  # unpublished until Super Admin activates
        monthly_price=float(monthly_price),
        yearly_price=float(yearly_price),
        student_limit=student_limit,
        staff_limit=staff_limit,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


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
) -> Package:
    plan = get_plan(db, plan_id)
    if name is not None:
        normalized = _normalize_name(name)
        _ensure_name_available(db, normalized, exclude_id=plan.id)
        plan.name = normalized
    if description is not None:
        plan.description = description[:255]
    if monthly_price is not None or yearly_price is not None:
        mp = float(monthly_price) if monthly_price is not None else float(plan.monthly_price or 0)
        yp = float(yearly_price) if yearly_price is not None else float(plan.yearly_price or 0)
        _validate_prices(mp, yp)
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
    db.commit()
    db.refresh(plan)
    return plan


def set_plan_status(db: Session, plan_id: int, *, status: int) -> Package:
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise PlanServiceError("Invalid status", status_code=422)
    plan = get_plan(db, plan_id)
    plan.status = status
    plan.updated_at = _utcnow()
    db.commit()
    db.refresh(plan)
    return plan
