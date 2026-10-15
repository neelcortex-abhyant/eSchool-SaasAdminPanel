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
    country_code: str | None = None,
    country_code_set: bool = False,
    gender: str | None = None,
    gender_set: bool = False,
    image: str | None = None,
    image_set: bool = False,
    dob=None,
    dob_set: bool = False,
    current_address: str | None = None,
    current_address_set: bool = False,
    permanent_address: str | None = None,
    permanent_address_set: bool = False,
    two_factor_enabled: int | None = None,
    two_factor_set: bool = False,
) -> User:
    """Update only the authenticated user's profile fields."""
    if first_name is not None:
        user.first_name = first_name.strip()
    if last_name is not None:
        user.last_name = last_name.strip()
    if mobile_set:
        user.mobile = mobile.strip() if mobile else None
    if country_code_set:
        user.country_code = country_code.strip() if country_code else None
    if gender_set:
        user.gender = gender
    if image_set:
        user.image = image.strip() if image else None
    if dob_set:
        user.dob = dob
    if current_address_set:
        user.current_address = current_address.strip() if current_address else None
    if permanent_address_set:
        user.permanent_address = permanent_address.strip() if permanent_address else None
    if two_factor_set and two_factor_enabled is not None:
        user.two_factor_enabled = two_factor_enabled
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
