from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify bcrypt hashes including Laravel `$2y$` prefixes."""
    try:
        raw = password_hash.encode()
        if password_hash.startswith("$2y$"):
            raw = ("$2b$" + password_hash[4:]).encode()
        return bcrypt.checkpw(password.encode(), raw)
    except ValueError:
        return False


def new_plain_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def session_serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt="eschool-admin-session")


def sign_session(payload: dict) -> str:
    return session_serializer().dumps(payload)


def read_session(token: str) -> dict | None:
    settings = get_settings()
    try:
        return session_serializer().loads(token, max_age=settings.session_lifetime_minutes * 60)
    except (BadSignature, SignatureExpired):
        return None


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def expires_at(minutes: int) -> datetime:
    return utcnow() + timedelta(minutes=minutes)
