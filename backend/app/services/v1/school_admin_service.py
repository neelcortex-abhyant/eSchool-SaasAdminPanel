"""School Admin management under a Super Admin–owned school (v1_users)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tables import School
from app.models.v1.admin_role import UserAdminRole
from app.models.v1.reset_token import PasswordResetToken
from app.models.v1.roles import ROLE_SCHOOL_ADMIN
from app.models.v1.session import AuthSession
from app.models.v1.user import STATUS_ACTIVE, STATUS_INACTIVE, User
from app.services.v1 import rbac
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


def _email_taken(db: Session, normalized_email: str) -> bool:
    return db.scalar(select(User.id).where(User.email == normalized_email)) is not None


def create_school_admin(
    db: Session,
    school_id: int,
    *,
    email: str,
    password: str | None,
    first_name: str,
    last_name: str,
    mobile: str | None,
    roles: list[str] | None = None,
    status: int = STATUS_ACTIVE,
    commit: bool = True,
) -> User:
    """Create a school_admin. password=None leaves an unusable password until the
    admin sets one through an invitation link. roles=None means the default role."""
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise SchoolAdminServiceError("Invalid status", status_code=422)
    if roles is not None:
        try:
            roles = rbac.normalize_roles(roles)
        except rbac.RbacError as exc:
            raise SchoolAdminServiceError(exc.detail, status_code=exc.status_code) from exc
    school = get_school(db, school_id)
    normalized = normalize_email(email)
    if _email_taken(db, normalized):
        raise SchoolAdminServiceError("Email already registered", status_code=409)

    user = User(
        email=normalized,
        # Nobody knows the random password; the invitation link replaces it.
        password_hash=hash_password(password if password is not None else secrets.token_urlsafe(32)),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        mobile=mobile.strip() if mobile else None,
        role=ROLE_SCHOOL_ADMIN,
        school_id=school.id,
        status=status,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        # Another request inserted the same email after the check above. The
        # failed flush leaves the session unusable, so the caller's work is lost too.
        db.rollback()
        if _email_taken(db, normalized):
            raise SchoolAdminServiceError("Email already registered", status_code=409) from None
        raise
    if roles is not None:
        rbac.set_roles(db, user, roles)
    if not school.v1_admin_id:
        school.v1_admin_id = str(user.id)
    if commit:
        db.commit()
        db.refresh(user)
    return user


ADMIN_SORT_HELP = "name, -name, created_at, or -created_at. Omitted sort is -created_at. id is the tie-breaker."

_ADMIN_SORTS = {
    "name": (func.lower(User.first_name).asc(), func.lower(User.last_name).asc(), User.id.asc()),
    "-name": (func.lower(User.first_name).desc(), func.lower(User.last_name).desc(), User.id.desc()),
    "created_at": (User.created_at.asc(), User.id.asc()),
    "-created_at": (User.created_at.desc(), User.id.desc()),
}


def list_school_admins(
    db: Session,
    school_id: int | None = None,
    *,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    status: int | None = None,
    role: str | None = None,
    sort: str | None = None,
) -> tuple[list[User], int]:
    """School admins, optionally for one school. Omitted sort is newest first."""
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    if school_id is not None:
        get_school(db, school_id)

    conditions = [User.role == ROLE_SCHOOL_ADMIN]
    if school_id is not None:
        conditions.append(User.school_id == school_id)
    if status is not None:
        if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
            raise SchoolAdminServiceError("Invalid status", status_code=422)
        conditions.append(User.status == status)
    if q and q.strip():
        like = f"%{q.strip()}%"
        conditions.append(
            or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
                func.concat(User.first_name, " ", User.last_name).ilike(like),
            )
        )
    if role:
        if role not in rbac.ADMIN_ROLES:
            raise SchoolAdminServiceError("Invalid role", status_code=422)
        holds = exists().where(UserAdminRole.user_id == User.id, UserAdminRole.role == role)
        if role == rbac.DEFAULT_ADMIN_ROLE:
            # Admins without any role rows hold the default role.
            holds = or_(holds, ~exists().where(UserAdminRole.user_id == User.id))
        conditions.append(holds)

    sort_key = (sort or "").strip() or "-created_at"
    if sort_key not in _ADMIN_SORTS:
        raise SchoolAdminServiceError("Invalid sort", status_code=422)

    total = int(db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0)
    rows = list(
        db.scalars(
            select(User)
            .where(*conditions)
            .order_by(*_ADMIN_SORTS[sort_key])
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def describe_admins(db: Session, users: list[User]) -> list[dict]:
    """Response fields for school admins, with roles and school names loaded in batch."""
    if not users:
        return []
    stored: dict[uuid.UUID, set[str]] = {}
    for user_id, role in db.execute(
        select(UserAdminRole.user_id, UserAdminRole.role).where(
            UserAdminRole.user_id.in_([u.id for u in users])
        )
    ):
        stored.setdefault(user_id, set()).add(role)
    school_ids = {u.school_id for u in users if u.school_id is not None}
    names = (
        dict(db.execute(select(School.id, School.name).where(School.id.in_(school_ids))).all())
        if school_ids
        else {}
    )
    items = []
    for user in users:
        roles = [key for key in rbac.ADMIN_ROLES if key in stored.get(user.id, set())]
        roles = roles or [rbac.DEFAULT_ADMIN_ROLE]
        items.append(
            {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "mobile": user.mobile,
                "role": user.role,
                "school_id": user.school_id,
                "school_name": names.get(user.school_id),
                "status": user.status,
                "roles": roles,
                "permissions": rbac.permissions_for_roles(roles),
                "created_at": user.created_at,
            }
        )
    return items


def describe_admin(db: Session, user: User) -> dict:
    return describe_admins(db, [user])[0]


def get_school_admin(db: Session, school_id: int, admin_id: uuid.UUID) -> User:
    return _get_school_admin(db, school_id, admin_id)


def revoke_sessions(db: Session, user_id: uuid.UUID) -> int:
    """Revoke every open session of the user. Does not commit. Returns how many."""
    now = datetime.now(timezone.utc)
    count = 0
    for session in db.scalars(
        select(AuthSession).where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
    ):
        session.revoked_at = now
        count += 1
    return count


def expire_reset_tokens(db: Session, user_id: uuid.UUID) -> None:
    """Mark the user's unused reset and setup links as used. Does not commit."""
    now = datetime.now(timezone.utc)
    for token in db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id, PasswordResetToken.used_at.is_(None)
        )
    ):
        token.used_at = now


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
    commit: bool = True,
) -> tuple[User, list[str]]:
    """Update profile fields. Returns the user and the names of fields that changed."""
    user = _get_school_admin(db, school_id, admin_id)
    changed: list[str] = []
    if first_name is not None and first_name.strip() != user.first_name:
        user.first_name = first_name.strip()
        changed.append("first_name")
    if last_name is not None and last_name.strip() != user.last_name:
        user.last_name = last_name.strip()
        changed.append("last_name")
    if mobile_set:
        new_mobile = mobile.strip() if mobile else None
        if new_mobile != user.mobile:
            user.mobile = new_mobile
            changed.append("mobile")
    if password is not None:
        if len(password) < 8:
            raise SchoolAdminServiceError("Password must be at least 8 characters", status_code=422)
        user.password_hash = hash_password(password)
        # A new password ends every existing sign-in and any pending reset link.
        revoke_sessions(db, user.id)
        expire_reset_tokens(db, user.id)
        changed.append("password")
    # Never allow school_id, role or email changes here.
    db.flush()
    if commit:
        db.commit()
        db.refresh(user)
    return user, changed


def set_school_admin_status(
    db: Session,
    school_id: int,
    admin_id: uuid.UUID,
    *,
    status: int,
    commit: bool = True,
) -> tuple[User, int, int]:
    """Set active/inactive. Returns the user, the previous status and sessions revoked.

    Deactivation revokes sessions and unused reset/setup links. Records are kept.
    """
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise SchoolAdminServiceError("Invalid status", status_code=422)
    user = _get_school_admin(db, school_id, admin_id)
    previous = user.status
    user.status = status
    revoked = 0
    if status == STATUS_INACTIVE:
        revoked = revoke_sessions(db, user.id)
        expire_reset_tokens(db, user.id)
    db.flush()
    if commit:
        db.commit()
        db.refresh(user)
    return user, previous, revoked


def set_school_admin_roles(
    db: Session,
    school_id: int,
    admin_id: uuid.UUID,
    *,
    roles: list[str],
) -> tuple[User, list[str], list[str]]:
    """Replace the admin's roles. Does not commit. Returns the user, previous and new roles."""
    user = _get_school_admin(db, school_id, admin_id)
    try:
        previous, new_roles = rbac.set_roles(db, user, roles)
    except rbac.RbacError as exc:
        raise SchoolAdminServiceError(exc.detail, status_code=exc.status_code) from exc
    return user, previous, new_roles


def count_school_admins(db: Session, school_id: int) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == ROLE_SCHOOL_ADMIN, User.school_id == school_id)
        )
        or 0
    )
