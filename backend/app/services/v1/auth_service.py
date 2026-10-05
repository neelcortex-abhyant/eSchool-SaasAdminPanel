from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_token, new_plain_token, verify_password
from app.models.v1.session import AuthSession
from app.models.v1.user import User


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

    session.last_used_at = now
    db.commit()
    return user, session


def logout(db: Session, session: AuthSession) -> None:
    if session.revoked_at is None:
        session.revoked_at = _utcnow()
        db.commit()
