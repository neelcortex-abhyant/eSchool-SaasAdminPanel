from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_token, new_plain_token, verify_password
from app.models.tables import School
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN, ROLE_USER
from app.models.v1.session import AuthSession
from app.models.v1.user import STATUS_ACTIVE, User
from app.services.v1 import audit_service


class AuthError(Exception):
    def __init__(self, detail: str, status_code: int = 401):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


@dataclass
class IssuedSession:
    plain_token: str
    expires_at: datetime
    user: User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_session(db: Session, user: User) -> IssuedSession:
    settings = get_settings()
    plain = new_plain_token()
    expires = _utcnow() + timedelta(minutes=settings.v1_session_ttl_minutes)
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(plain),
        expires_at=expires,
    )
    db.add(session)
    db.commit()
    db.refresh(user)
    return IssuedSession(plain_token=plain, expires_at=expires, user=user)


def signup(
    db: Session,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    mobile: str | None,
) -> IssuedSession:
    normalized = normalize_email(email)
    existing = db.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        raise AuthError("Email already registered", status_code=409)

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        mobile=mobile.strip() if mobile else None,
        # Public signup must never create Super Admin — role is not client-selectable.
        role=ROLE_USER,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return create_session(db, user)


def bootstrap_super_admin(db: Session) -> User | None:
    """Promote configured email to super_admin if that v1 user already exists.

    Secure: does not create accounts, does not set passwords, ignores empty env.
    """
    settings = get_settings()
    configured = (settings.v1_super_admin_email or "").strip()
    if not configured:
        return None
    normalized = normalize_email(configured)
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None:
        return None
    if user.role != ROLE_SUPER_ADMIN:
        user.role = ROLE_SUPER_ADMIN
        db.commit()
        db.refresh(user)
    return user


def count_super_admins(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(User).where(User.role == ROLE_SUPER_ADMIN)) or 0)


def register_super_admin(
    db: Session,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    mobile: str | None,
) -> IssuedSession:
    """Create a Super Admin via the same v1 user/session stack.

    Allowed only when:
    - no super_admin exists yet (first bootstrap), or
    - email matches V1_SUPER_ADMIN_EMAIL.
    Public /auth/signup never assigns super_admin.
    """
    settings = get_settings()
    normalized = normalize_email(email)
    configured = normalize_email(settings.v1_super_admin_email or "")
    allowed = count_super_admins(db) == 0 or (configured and normalized == configured)
    if not allowed:
        raise AuthError("Super Admin registration is not allowed", status_code=403)

    existing = db.scalar(select(User).where(User.email == normalized))
    if existing is not None:
        if existing.role == ROLE_SUPER_ADMIN:
            raise AuthError("Email already registered", status_code=409)
        # Promote an existing normal user only when email is the configured SA email.
        if configured and normalized == configured:
            existing.password_hash = hash_password(password)
            existing.first_name = first_name.strip()
            existing.last_name = last_name.strip()
            existing.mobile = mobile.strip() if mobile else existing.mobile
            existing.role = ROLE_SUPER_ADMIN
            db.commit()
            db.refresh(existing)
            return create_session(db, existing)
        raise AuthError("Email already registered", status_code=409)

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        mobile=mobile.strip() if mobile else None,
        role=ROLE_SUPER_ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return create_session(db, user)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(16))


def _check_credentials(user: User | None, password: str) -> bool:
    """bcrypt runs even for unknown emails, so timing does not reveal which emails exist."""
    if user is None:
        verify_password(password, _dummy_hash())
        return False
    return verify_password(password, user.password_hash)


def login(db: Session, *, email: str, password: str) -> IssuedSession:
    normalized = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized))
    if not _check_credentials(user, password):
        raise AuthError("Invalid email or password", status_code=401)
    if user.status != STATUS_ACTIVE:
        raise AuthError("Account inactive", status_code=403)
    assert_school_admin_login_allowed(db, user)
    return create_session(db, user)


SCHOOL_PENDING_DETAIL = "This school is waiting for approval. You can sign in after it is activated."
SCHOOL_SUSPENDED_DETAIL = "School access is suspended"
SCHOOL_SETUP_INCOMPLETE_DETAIL = (
    "This school has not finished setup. Ask the Super Admin to activate it, then sign in again."
)
SUBSCRIPTION_BLOCKED_DETAIL = "Subscription access is not available"


def school_admin_access_error(db: Session, user: User) -> AuthError | None:
    """The one rule for whether a school_admin may use the School Admin panel.

    Login (``assert_school_admin_login_allowed``) and every ``/school-admin`` route
    (``deps.require_school_admin``) both call this, so a login that succeeds is never
    followed by 403s on the dashboard. Returns None when access is allowed.
    """
    from app.services.v1.subscription_access import subscription_expiry_blocks_access

    if user.status != STATUS_ACTIVE:
        return AuthError("Account inactive", status_code=403)
    if user.school_id is None:
        return AuthError("No school assigned", status_code=403)
    school = db.get(School, user.school_id)
    if school is None or school.deleted_at is not None:
        return AuthError(SCHOOL_SUSPENDED_DETAIL, status_code=403)
    active = school.status == 1
    installed = school.installed == 1
    if not active and not installed:
        return AuthError(SCHOOL_PENDING_DETAIL, status_code=403)
    if not active:
        return AuthError(SCHOOL_SUSPENDED_DETAIL, status_code=403)
    if not installed:
        return AuthError(SCHOOL_SETUP_INCOMPLETE_DETAIL, status_code=403)
    if subscription_expiry_blocks_access(user.school_id):
        return AuthError(SUBSCRIPTION_BLOCKED_DETAIL, status_code=403)
    return None


def assert_school_admin_login_allowed(db: Session, user: User) -> None:
    """Block a school admin whose panel would refuse them (same rule as the routes)."""
    if user.role != ROLE_SCHOOL_ADMIN:
        return
    error = school_admin_access_error(db, user)
    if error is not None:
        raise error


def login_super_admin(db: Session, *, email: str, password: str) -> IssuedSession:
    """Login that requires role=super_admin after credential check."""
    normalized = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized))
    if not _check_credentials(user, password):
        raise AuthError("Invalid email or password", status_code=401)
    # Same answer as a wrong password, so this endpoint does not reveal other roles' accounts.
    if user.role != ROLE_SUPER_ADMIN:
        raise AuthError("Invalid email or password", status_code=401)
    if user.status != STATUS_ACTIVE:
        raise AuthError("Account inactive", status_code=403)
    return create_session(db, user)


def resolve_user_from_token(db: Session, plain_token: str) -> tuple[User, AuthSession]:
    token_hash = hash_token(plain_token)
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash))
    if session is None:
        raise AuthError("Not authenticated", status_code=401)
    if session.revoked_at is not None:
        raise AuthError("Not authenticated", status_code=401)

    now = _utcnow()
    expires = session.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise AuthError("Not authenticated", status_code=401)

    user = db.get(User, session.user_id)
    if user is None:
        raise AuthError("Not authenticated", status_code=401)
    # Deactivated accounts must not keep using existing opaque sessions.
    if user.status != STATUS_ACTIVE:
        raise AuthError("Account inactive", status_code=403)

    if _last_used_is_stale(session.last_used_at, now):
        session.last_used_at = now
        db.commit()
    return user, session


# How often an active session's last_used_at is written. Writing it on every request
# costs a DB commit per API call (one cross-region round trip each on Render + Neon).
LAST_USED_WRITE_INTERVAL = timedelta(minutes=5)


def _last_used_is_stale(last_used_at: datetime | None, now: datetime) -> bool:
    if last_used_at is None:
        return True
    if last_used_at.tzinfo is None:
        last_used_at = last_used_at.replace(tzinfo=timezone.utc)
    return now - last_used_at >= LAST_USED_WRITE_INTERVAL


def change_password(
    db: Session,
    user: User,
    session: AuthSession,
    *,
    current_password: str,
    new_password: str,
) -> None:
    """Replace the signed-in user's password after checking the current one."""
    if not verify_password(current_password, user.password_hash):
        raise AuthError("Current password is incorrect.", status_code=400)
    if current_password == new_password:
        raise AuthError("Choose a different password.", status_code=422)
    user.password_hash = hash_password(new_password)
    now = _utcnow()
    others = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user.id,
            AuthSession.id != session.id,
            AuthSession.revoked_at.is_(None),
        )
    )
    revoked = 0
    for other in others:
        other.revoked_at = now
        revoked += 1
    db.add(user)
    db.flush()
    # Same commit as the password change. Never records the password.
    audit_service.record_audit(
        db,
        actor=user,
        action="auth.password_change",
        entity_type="user",
        entity_id=user.id,
        school_id=user.school_id,
        metadata={"other_sessions_revoked": revoked},
    )


def logout(db: Session, session: AuthSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = _utcnow()
        db.commit()
