from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.v1.user import User


def update_profile(
    db: Session,
    user: User,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    mobile: str | None = None,
    mobile_set: bool = False,
) -> User:
    """Update only the authenticated user's profile fields."""
    if first_name is not None:
        user.first_name = first_name.strip()
    if last_name is not None:
        user.last_name = last_name.strip()
    if mobile_set:
        user.mobile = mobile.strip() if mobile else None
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
