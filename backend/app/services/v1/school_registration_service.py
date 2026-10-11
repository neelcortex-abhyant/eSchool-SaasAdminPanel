"""Public school registration. Creates a pending school and its first school admin.

Does not issue a session, start a subscription, or mark the school active.
A super admin activates the school before the administrator can sign in.
"""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from app.models.tables import School
from app.services.v1 import audit_service
from app.services.v1.school_admin_service import SchoolAdminServiceError, create_school_admin
from app.services.v1.school_service import (
    INSTALLED_NO,
    STATUS_INACTIVE,
    SchoolServiceError,
    create_school,
)

_ATTEMPTS: dict[str, list[float]] = {}
_LIMIT = 8
_WINDOW_SECONDS = 3600


class SchoolRegistrationError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def reset_registration_limits() -> None:
    _ATTEMPTS.clear()


def compose_address(*, address: str, city: str, state: str, country: str, postal_code: str) -> str:
    parts = [address, city, state, postal_code, country]
    return ", ".join(part.strip() for part in parts if part and part.strip())


def _limit(key: str) -> None:
    now = time.monotonic()
    recent = [stamp for stamp in _ATTEMPTS.get(key, []) if now - stamp < _WINDOW_SECONDS]
    if len(recent) >= _LIMIT:
        _ATTEMPTS[key] = recent
        raise SchoolRegistrationError("Too many registration attempts. Try again later.", status_code=429)
    recent.append(now)
    _ATTEMPTS[key] = recent


def register_school(
    db: Session,
    *,
    name: str,
    support_email: str,
    support_phone: str,
    address: str,
    city: str,
    state: str,
    country: str,
    postal_code: str,
    tagline: str,
    logo: str,
    domain: str | None,
    admin_first_name: str,
    admin_last_name: str,
    admin_email: str,
    admin_mobile: str | None,
    admin_password: str,
    terms_accepted: bool,
) -> School:
    if terms_accepted is not True:
        raise SchoolRegistrationError("Accept the terms and conditions to continue.", status_code=422)
    full_address = compose_address(
        address=address,
        city=city,
        state=state,
        country=country,
        postal_code=postal_code,
    )
    if len(full_address) > 255:
        raise SchoolRegistrationError(
            "Address, city, state, country, and postal code together must be 255 characters or fewer.",
            status_code=422,
        )
    _limit(support_email.strip().lower())
    _limit(admin_email.strip().lower())

    try:
        school = create_school(
            db,
            name=name,
            address=full_address,
            support_phone=support_phone,
            support_email=support_email,
            tagline=tagline,
            logo=logo,
            domain=domain,
            status=STATUS_INACTIVE,
            installed=INSTALLED_NO,
            commit=False,
        )
        create_school_admin(
            db,
            school.id,
            email=admin_email,
            password=admin_password,
            first_name=admin_first_name,
            last_name=admin_last_name,
            mobile=admin_mobile,
            commit=False,
        )
    except (SchoolServiceError, SchoolAdminServiceError):
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    audit_service.record_audit(
        db,
        actor=None,
        action="school.register",
        entity_type="school",
        entity_id=school.id,
        school_id=school.id,
        metadata={"name": school.name, "status": "pending_approval"},
    )
    db.refresh(school)
    return school
