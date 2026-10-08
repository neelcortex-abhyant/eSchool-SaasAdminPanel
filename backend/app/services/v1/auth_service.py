from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_token, new_plain_token, verify_password
from app.models.v1.roles import ROLE_SUPER_ADMIN, ROLE_USER
from app.models.v1.session import AuthSession
from app.models.v1.user import STATUS_ACTIVE, User


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


def login(db: Session, *, email: str, password: str) -> IssuedSession:
    normalized = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password", status_code=401)
    if user.status != STATUS_ACTIVE:
        raise AuthError("Account inactive", status_code=403)
    return create_session(db, user)


def login_super_admin(db: Session, *, email: str, password: str) -> IssuedSession:
    """Login that requires role=super_admin after credential check."""
    normalized = normalize_email(email)
    user = db.scalar(select(User).where(User.email == normalized))
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password", status_code=401)
    if user.role != ROLE_SUPER_ADMIN:
        raise AuthError("Forbidden", status_code=403)
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

    session.last_used_at = now
    db.commit()
    return user, session


def logout(db: Session, session: AuthSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = _utcnow()
        db.commit()
