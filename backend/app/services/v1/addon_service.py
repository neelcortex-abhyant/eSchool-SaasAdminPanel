"""Super Admin add-on catalog + school assignments (Phase 6)."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import Addon, AddonSubscription, School, Subscription
from app.services.v1.subscription_service import SUB_STATUS_ACTIVE

STATUS_INACTIVE = 0
STATUS_ACTIVE = 1


class AddonServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise AddonServiceError("Addon name is required", status_code=422)
    return cleaned[:255]


def _ensure_name_available(db: Session, name: str, *, exclude_id: int | None = None) -> None:
    query = select(Addon.id).where(Addon.name == name, Addon.deleted_at.is_(None))
    if exclude_id is not None:
        query = query.where(Addon.id != exclude_id)
    if db.scalar(query) is not None:
        raise AddonServiceError("Addon name already in use", status_code=409)


def _get_school(db: Session, school_id: int) -> School:
    school = db.get(School, school_id)
    if school is None or school.deleted_at is not None:
        raise AddonServiceError("School not found", status_code=404)
    return school


def get_addon(db: Session, addon_id: int, *, include_deleted: bool = False) -> Addon:
    addon = db.get(Addon, addon_id)
    if addon is None or (not include_deleted and addon.deleted_at is not None):
        raise AddonServiceError("Addon not found", status_code=404)
    return addon


def create_addon(
    db: Session,
    *,
    name: str,
    description: str = "",
    price: float = 0.0,
) -> Addon:
    normalized = _normalize_name(name)
    _ensure_name_available(db, normalized)
    if price < 0:
        raise AddonServiceError("price must be >= 0", status_code=422)
    now = _utcnow()
    addon = Addon(
        name=normalized,
        description=(description or "")[:255],
        price=float(price),
        status=STATUS_INACTIVE,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(addon)
    db.commit()
    db.refresh(addon)
    return addon


def list_addons(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
    name: str | None = None,
) -> tuple[list[Addon], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = select(Addon).where(Addon.deleted_at.is_(None))
    count_query = select(func.count()).select_from(Addon).where(Addon.deleted_at.is_(None))
    if status is not None:
        query = query.where(Addon.status == status)
        count_query = count_query.where(Addon.status == status)
    if name:
        like = f"%{name.strip()}%"
        query = query.where(Addon.name.ilike(like))
        count_query = count_query.where(Addon.name.ilike(like))
    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(query.order_by(Addon.id.desc()).offset((page - 1) * page_size).limit(page_size))
    )
    return rows, total


def update_addon(
    db: Session,
    addon_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    price: float | None = None,
) -> Addon:
    addon = get_addon(db, addon_id)
    if name is not None:
        normalized = _normalize_name(name)
        _ensure_name_available(db, normalized, exclude_id=addon.id)
        addon.name = normalized
    if description is not None:
        addon.description = description[:255]
    if price is not None:
        if price < 0:
            raise AddonServiceError("price must be >= 0", status_code=422)
        addon.price = float(price)
    addon.updated_at = _utcnow()
    db.commit()
    db.refresh(addon)
    return addon


def set_addon_status(db: Session, addon_id: int, *, status: int) -> Addon:
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise AddonServiceError("Invalid status", status_code=422)
    addon = get_addon(db, addon_id)
    addon.status = status
    addon.updated_at = _utcnow()
    db.commit()
    db.refresh(addon)
    return addon


def _resolve_subscription(
    db: Session,
    school_id: int,
    subscription_id: int | None,
) -> Subscription:
    if subscription_id is not None:
        sub = db.get(Subscription, subscription_id)
        if (
            sub is None
            or sub.deleted_at is not None
            or sub.school_id != school_id
        ):
            raise AddonServiceError("Subscription not found", status_code=404)
        return sub
    sub = db.scalar(
        select(Subscription).where(
            Subscription.school_id == school_id,
            Subscription.status == SUB_STATUS_ACTIVE,
            Subscription.deleted_at.is_(None),
        )
    )
    if sub is None:
        raise AddonServiceError("School has no active subscription", status_code=409)
    return sub


def assign_addon(
    db: Session,
    school_id: int,
    *,
    addon_id: int,
    subscription_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> AddonSubscription:
    _get_school(db, school_id)
    addon = get_addon(db, addon_id)
    if addon.status != STATUS_ACTIVE:
        raise AddonServiceError("Addon is not active", status_code=422)
    sub = _resolve_subscription(db, school_id, subscription_id)
    if start_date and end_date and end_date < start_date:
        raise AddonServiceError("end_date must be on or after start_date", status_code=422)

    existing = db.scalar(
        select(AddonSubscription).where(
            AddonSubscription.school_id == school_id,
            AddonSubscription.addon_id == addon_id,
            AddonSubscription.status == STATUS_ACTIVE,
            AddonSubscription.deleted_at.is_(None),
        )
    )
    if existing is not None:
        raise AddonServiceError("Addon already assigned to this school", status_code=409)

    now = _utcnow()
    row = AddonSubscription(
        school_id=school_id,
        addon_id=addon_id,
        subscription_id=sub.id,
        status=STATUS_ACTIVE,
        start_date=start_date or sub.start_date,
        end_date=end_date or sub.end_date,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_school_addons(
    db: Session,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
) -> tuple[list[AddonSubscription], int]:
    _get_school(db, school_id)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = select(AddonSubscription).where(
        AddonSubscription.school_id == school_id,
        AddonSubscription.deleted_at.is_(None),
    )
    count_query = (
        select(func.count())
        .select_from(AddonSubscription)
        .where(
            AddonSubscription.school_id == school_id,
            AddonSubscription.deleted_at.is_(None),
        )
    )
    if status is not None:
        query = query.where(AddonSubscription.status == status)
        count_query = count_query.where(AddonSubscription.status == status)
    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(
            query.order_by(AddonSubscription.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def get_school_addon(
    db: Session,
    school_id: int,
    assignment_id: int,
) -> AddonSubscription:
    _get_school(db, school_id)
    row = db.get(AddonSubscription, assignment_id)
    if (
        row is None
        or row.deleted_at is not None
        or row.school_id != school_id
    ):
        raise AddonServiceError("School addon assignment not found", status_code=404)
    return row


def set_school_addon_status(
    db: Session,
    school_id: int,
    assignment_id: int,
    *,
    status: int,
) -> AddonSubscription:
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise AddonServiceError("Invalid status", status_code=422)
    row = get_school_addon(db, school_id, assignment_id)
    if status == STATUS_ACTIVE:
        dup = db.scalar(
            select(AddonSubscription).where(
                AddonSubscription.school_id == school_id,
                AddonSubscription.addon_id == row.addon_id,
                AddonSubscription.status == STATUS_ACTIVE,
                AddonSubscription.deleted_at.is_(None),
                AddonSubscription.id != row.id,
            )
        )
        if dup is not None:
            raise AddonServiceError("Addon already assigned to this school", status_code=409)
    row.status = status
    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return row
