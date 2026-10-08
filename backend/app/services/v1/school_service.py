"""Super Admin school CRUD — reuses legacy School model (no duplicate table)."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import School

# Verified in FastAPI (mobile_auth / admin_data / school_is_ready):
# status=1 active; status=0 blocks mobile login.
# installed=1 required for school-code admin login / school_is_ready.
STATUS_ACTIVE = 1
STATUS_INACTIVE = 0
INSTALLED_YES = 1
INSTALLED_NO = 0


class SchoolServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_code(code: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "", code.strip().upper())
    if not cleaned:
        raise SchoolServiceError("Invalid school code", status_code=422)
    return cleaned[:255]


def _generate_code(db: Session, name: str) -> str:
    base = _normalize_code(re.sub(r"\s+", "", name)[:12] or "SCH")
    for _ in range(20):
        candidate = f"{base}{secrets.token_hex(2).upper()}"
        exists = db.scalar(select(School.id).where(School.code == candidate))
        if exists is None:
            return candidate
    raise SchoolServiceError("Could not allocate unique school code", status_code=500)


def _ensure_code_available(db: Session, code: str, *, exclude_id: int | None = None) -> None:
    query = select(School.id).where(School.code == code)
    if exclude_id is not None:
        query = query.where(School.id != exclude_id)
    if db.scalar(query) is not None:
        raise SchoolServiceError("School code already in use", status_code=409)


def get_school(db: Session, school_id: int, *, include_deleted: bool = False) -> School:
    school = db.get(School, school_id)
    if school is None or (not include_deleted and school.deleted_at is not None):
        raise SchoolServiceError("School not found", status_code=404)
    return school


def create_school(
    db: Session,
    *,
    name: str,
    address: str = "",
    support_phone: str = "",
    support_email: str = "",
    tagline: str = "",
    logo: str = "",
    code: str | None = None,
    domain: str | None = None,
) -> School:
    now = _utcnow()
    if code:
        normalized = _normalize_code(code)
        _ensure_code_available(db, normalized)
    else:
        normalized = _generate_code(db, name)

    school = School(
        name=name.strip(),
        address=address or "",
        support_phone=support_phone or "",
        support_email=support_email or "",
        tagline=tagline or "",
        logo=logo or "",
        code=normalized,
        domain=domain.strip() if domain else None,
        status=STATUS_ACTIVE,
        installed=INSTALLED_YES,
        admin_id=None,
        database_name=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


def list_schools(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
    code: str | None = None,
    name: str | None = None,
    include_deleted: bool = False,
) -> tuple[list[School], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = select(School)
    count_query = select(func.count()).select_from(School)

    if not include_deleted:
        query = query.where(School.deleted_at.is_(None))
        count_query = count_query.where(School.deleted_at.is_(None))
    if status is not None:
        query = query.where(School.status == status)
        count_query = count_query.where(School.status == status)
    if code:
        query = query.where(School.code == _normalize_code(code))
        count_query = count_query.where(School.code == _normalize_code(code))
    if name:
        like = f"%{name.strip()}%"
        query = query.where(School.name.ilike(like))
        count_query = count_query.where(School.name.ilike(like))

    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(query.order_by(School.id.desc()).offset((page - 1) * page_size).limit(page_size))
    )
    return rows, total


def update_school(
    db: Session,
    school_id: int,
    *,
    name: str | None = None,
    address: str | None = None,
    support_phone: str | None = None,
    support_email: str | None = None,
    tagline: str | None = None,
    logo: str | None = None,
    code: str | None = None,
    domain: str | None = None,
) -> School:
    school = get_school(db, school_id)
    if name is not None:
        school.name = name.strip()
    if address is not None:
        school.address = address
    if support_phone is not None:
        school.support_phone = support_phone
    if support_email is not None:
        school.support_email = support_email
    if tagline is not None:
        school.tagline = tagline
    if logo is not None:
        school.logo = logo
    if code is not None:
        normalized = _normalize_code(code)
        _ensure_code_available(db, normalized, exclude_id=school.id)
        school.code = normalized
    if domain is not None:
        school.domain = domain.strip() or None
    school.updated_at = _utcnow()
    db.commit()
    db.refresh(school)
    return school


def soft_delete_school(db: Session, school_id: int) -> School:
    school = get_school(db, school_id)
    school.deleted_at = _utcnow()
    school.updated_at = school.deleted_at
    db.commit()
    db.refresh(school)
    return school


def activate_school(db: Session, school_id: int) -> School:
    school = get_school(db, school_id)
    school.status = STATUS_ACTIVE
    school.installed = INSTALLED_YES
    school.updated_at = _utcnow()
    db.commit()
    db.refresh(school)
    return school


def suspend_school(db: Session, school_id: int) -> School:
    """status=0 — blocks mobile login (verified in mobile_auth)."""
    school = get_school(db, school_id)
    school.status = STATUS_INACTIVE
    school.updated_at = _utcnow()
    db.commit()
    db.refresh(school)
    return school


def deactivate_school(db: Session, school_id: int) -> School:
    """status=0 and installed=0 — blocks mobile + school-code admin readiness."""
    school = get_school(db, school_id)
    school.status = STATUS_INACTIVE
    school.installed = INSTALLED_NO
    school.updated_at = _utcnow()
    db.commit()
    db.refresh(school)
    return school


def provision_school(db: Session, school_id: int) -> tuple[School, bool]:
    """Idempotent shared-Neon provisioning (no physical DB create).

    Ensures school is active/installed and has a default session year.
    Returns (school, created_fresh) where created_fresh is True only on first provision.
    """
    from datetime import date

    from app.models.tables import SessionYear

    school = get_school(db, school_id)
    first_time = school.provisioned_at is None
    now = _utcnow()

    school.status = STATUS_ACTIVE
    school.installed = INSTALLED_YES
    if first_time:
        school.provisioned_at = now
    school.updated_at = now

    year = db.scalar(
        select(SessionYear).where(
            SessionYear.school_id == school.id,
            SessionYear.default == 1,
            SessionYear.deleted_at.is_(None),
        )
    )
    if year is None:
        y = now.year
        db.add(
            SessionYear(
                name=str(y),
                default=1,
                start_date=date(y, 1, 1),
                end_date=date(y, 12, 31),
                school_id=school.id,
                created_at=now,
                updated_at=now,
            )
        )

    db.commit()
    db.refresh(school)
    return school, first_time
