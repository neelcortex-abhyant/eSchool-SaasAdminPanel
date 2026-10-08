"""School Admin management under a Super Admin–owned school (v1_users)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.v1.roles import ROLE_SCHOOL_ADMIN
from app.models.v1.session import AuthSession
from app.models.v1.user import STATUS_ACTIVE, STATUS_INACTIVE, User
from app.services.v1.auth_service import normalize_email
from app.services.v1.school_service import SchoolServiceError, get_school


class SchoolAdminServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _get_school_admin(db: Session, school_id: int, admin_id: uuid.UUID) -> User:
    get_school(db, school_id)  # 404 if school missing
    user = db.get(User, admin_id)
    if (
        user is None
        or user.role != ROLE_SCHOOL_ADMIN
        or user.school_id != school_id
    ):
        raise SchoolAdminServiceError("School admin not found", status_code=404)
    return user


def create_school_admin(
    db: Session,
    school_id: int,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    mobile: str | None,
) -> User:
    school = get_school(db, school_id)
    normalized = normalize_email(email)
    existing = db.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        raise SchoolAdminServiceError("Email already registered", status_code=409)

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        mobile=mobile.strip() if mobile else None,
        role=ROLE_SCHOOL_ADMIN,
        school_id=school.id,
        status=STATUS_ACTIVE,
    )
    db.add(user)
    db.flush()
    if not school.v1_admin_id:
        school.v1_admin_id = str(user.id)
    db.commit()
    db.refresh(user)
    return user


def list_school_admins(db: Session, school_id: int) -> list[User]:
    get_school(db, school_id)
    return list(
        db.scalars(
            select(User)
            .where(User.role == ROLE_SCHOOL_ADMIN, User.school_id == school_id)
            .order_by(User.created_at.desc())
        )
    )


def get_school_admin(db: Session, school_id: int, admin_id: uuid.UUID) -> User:
    return _get_school_admin(db, school_id, admin_id)


def update_school_admin(
    db: Session,
    school_id: int,
    admin_id: uuid.UUID,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    mobile: str | None = None,
    mobile_set: bool = False,
    password: str | None = None,
) -> User:
    user = _get_school_admin(db, school_id, admin_id)
    if first_name is not None:
        user.first_name = first_name.strip()
    if last_name is not None:
        user.last_name = last_name.strip()
    if mobile_set:
        user.mobile = mobile.strip() if mobile else None
    if password is not None:
        if len(password) < 8:
            raise SchoolAdminServiceError("Password must be at least 8 characters", status_code=422)
        user.password_hash = hash_password(password)
    # Never allow school_id or role changes here.
    db.commit()
    db.refresh(user)
    return user


def set_school_admin_status(
    db: Session,
    school_id: int,
    admin_id: uuid.UUID,
    *,
    status: int,
) -> User:
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise SchoolAdminServiceError("Invalid status", status_code=422)
    user = _get_school_admin(db, school_id, admin_id)
    user.status = status
    if status == STATUS_INACTIVE:
        now = datetime.now(timezone.utc)
        for session in db.scalars(
            select(AuthSession).where(
                AuthSession.user_id == user.id,
                AuthSession.revoked_at.is_(None),
            )
        ):
            session.revoked_at = now
    db.commit()
    db.refresh(user)
    return user


def count_school_admins(db: Session, school_id: int) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == ROLE_SCHOOL_ADMIN, User.school_id == school_id)
        )
        or 0
    )
