"""Password reset and invitation (password setup) links.

Tokens are random, single-use and expiring. Only their SHA-256 hash is stored.
Links point at settings.admin_reset_url, never at a client-supplied origin.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, hash_token, new_plain_token
from app.models.v1.reset_token import PURPOSE_RESET, PURPOSE_SETUP, PasswordResetToken
from app.models.v1.roles import ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN
from app.models.v1.user import STATUS_ACTIVE, User
from app.services.v1 import audit_service, auth_service, mailer
from app.services.v1.school_admin_service import expire_reset_tokens, revoke_sessions

INVALID_LINK = "Invalid or expired reset link."
# Roles that may recover a password through email.
_RECOVERABLE_ROLES = frozenset({ROLE_SCHOOL_ADMIN, ROLE_SUPER_ADMIN})


class PasswordResetError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


@dataclass
class PendingMail:
    """A message to send after the token is committed. Holds the plain link: never log it."""

    to: str
    subject: str
    body: str


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def issue_token(db: Session, user: User, purpose: str) -> str:
    """Create a new token, invalidating the user's earlier unused links. Does not commit."""
    settings = get_settings()
    minutes = settings.invite_ttl_minutes if purpose == PURPOSE_SETUP else settings.password_reset_ttl_minutes
    expire_reset_tokens(db, user.id)
    plain = new_plain_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(plain),
            purpose=purpose,
            expires_at=_utcnow() + timedelta(minutes=minutes),
        )
    )
    db.flush()
    return plain


def _link(plain: str) -> str:
    base = get_settings().admin_reset_url.strip()
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{urlencode({'token': plain})}"


def invitation_mail(user: User, plain: str) -> PendingMail:
    hours = get_settings().invite_ttl_minutes // 60
    return PendingMail(
        to=user.email,
        subject="Set up your eSchool admin account",
        body=(
            f"Hello {user.first_name},\n\n"
            "An eSchool School Admin account was created for you. "
            f"Set your password with this link (valid for {hours} hours, single use):\n\n"
            f"{_link(plain)}\n\n"
            "If you did not expect this email, you can ignore it."
        ),
    )


def reset_mail(user: User, plain: str) -> PendingMail:
    minutes = get_settings().password_reset_ttl_minutes
    return PendingMail(
        to=user.email,
        subject="Reset your eSchool password",
        body=(
            f"Hello {user.first_name},\n\n"
            f"Reset your password with this link (valid for {minutes} minutes, single use):\n\n"
            f"{_link(plain)}\n\n"
            "If you did not ask for a reset, you can ignore this email. Your password has not changed."
        ),
    )


def send(mail: PendingMail | None) -> bool:
    return mailer.send_mail(mail.to, mail.subject, mail.body) if mail is not None else False


def prepare_invitation(db: Session, user: User) -> PendingMail | None:
    """Issue a setup token for an active school admin. Does not commit or send.

    Returns None when mail is not configured or the account is inactive, so no
    link is created that nobody can receive or use.
    """
    if not get_settings().mail_configured or user.status != STATUS_ACTIVE:
        return None
    return invitation_mail(user, issue_token(db, user, PURPOSE_SETUP))


def request_reset(db: Session, email: str) -> PendingMail | None:
    """Commit a reset token for an eligible account and return the mail to send.

    The caller answers the same way whatever this returns, so the public
    response never reveals whether the email belongs to an account.
    """
    if not get_settings().mail_configured:
        return None
    user = db.scalar(select(User).where(User.email == auth_service.normalize_email(email)))
    if user is None or user.status != STATUS_ACTIVE or user.role not in _RECOVERABLE_ROLES:
        return None
    try:
        auth_service.assert_school_admin_login_allowed(db, user)
    except auth_service.AuthError:
        return None
    plain = issue_token(db, user, PURPOSE_RESET)
    db.commit()
    return reset_mail(user, plain)


def consume_token(db: Session, plain: str, new_password: str) -> User:
    """Set the password from a valid link. One commit: password, token, sessions, audit."""
    row = db.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(plain)).with_for_update()
    )
    now = _utcnow()
    if row is None or row.used_at is not None:
        raise PasswordResetError(INVALID_LINK)
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise PasswordResetError(INVALID_LINK)
    user = db.get(User, row.user_id)
    if user is None or user.status != STATUS_ACTIVE or user.role not in _RECOVERABLE_ROLES:
        raise PasswordResetError(INVALID_LINK)
    try:
        auth_service.assert_school_admin_login_allowed(db, user)
    except auth_service.AuthError:
        raise PasswordResetError(INVALID_LINK) from None

    user.password_hash = hash_password(new_password)
    expire_reset_tokens(db, user.id)  # marks this token used, plus any other pending link
    revoked = revoke_sessions(db, user.id)
    db.flush()
    audit_service.record_audit(
        db,
        actor=user,
        action="auth.password_reset",
        entity_type="user",
        entity_id=user.id,
        school_id=user.school_id,
        metadata={"purpose": row.purpose, "sessions_revoked": revoked},
    )
    return user
