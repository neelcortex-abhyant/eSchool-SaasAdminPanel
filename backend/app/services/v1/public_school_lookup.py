"""Unauthenticated public school website lookup (safe fields only)."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.tables import School
from app.services.v1.school_academics import AcademicError


def _status_label(status: int | None) -> str:
    # Match SCHOOL_DOMAINS_API_CONTRACT.md public payload.
    if status == 0:
        return "inactive"
    if status == 2:
        return "pending_approval"
    return "active"


def _slug_from_domain(domain: str | None, domain_type: str | None) -> str | None:
    if not domain or not str(domain).strip():
        return None
    host = str(domain).strip().lower()
    if domain_type == "custom":
        return host.split(".", 1)[0] or None
    # default / legacy: first label of stored FQDN (or whole value if no dot)
    return host.split(".", 1)[0] or host


def _public_payload(school: School) -> dict:
    domain = (school.domain or "").strip() or None
    domain_type = (school.domain_type or "").strip() or None
    verified = int(school.domain_verified or 0) == 1
    custom_domain = domain if domain_type == "custom" else None
    if domain_type == "custom":
        domain_status = "verified" if verified else "pending"
    elif domain:
        domain_status = "verified" if verified or domain_type in (None, "default") else "pending"
    else:
        domain_status = "not_started"

    return {
        "school_id": school.id,
        "name": school.name,
        "slug": _slug_from_domain(domain, domain_type),
        "tagline": school.tagline or None,
        "logo": school.logo or None,
        "address": school.address or None,
        "city": None,  # column not present yet — contract allows null
        "phone": school.support_phone or None,
        "email": school.support_email or None,
        "theme_primary": None,
        "theme_secondary": None,
        "about": None,
        "admissions_open": True,
        "status": _status_label(school.status),
        "setup_complete": bool(school.provisioned_at),
        "custom_domain": custom_domain,
        "domain_status": domain_status,
    }


def lookup_by_host(db: Session, host: str) -> dict:
    raw = (host or "").strip().lower()
    if not raw:
        raise AcademicError(422, "host is required")
    # Strip scheme/port/path if a full URL was passed.
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    raw = raw.split("/", 1)[0]
    raw = raw.split(":", 1)[0]
    if not raw:
        raise AcademicError(422, "host is required")

    school = (
        db.query(School)
        .filter(
            School.deleted_at.is_(None),
            School.domain.isnot(None),
            func.lower(func.btrim(School.domain)) == raw,
        )
        .first()
    )
    if school is None:
        raise AcademicError(404, "School not found")

    dtype = (school.domain_type or "").strip() or None
    if dtype == "custom" and int(school.domain_verified or 0) != 1:
        raise AcademicError(404, "School not found")

    return _public_payload(school)


def lookup_by_code(db: Session, code: str) -> dict:
    """Lookup by public school ``code`` (tenant identifier), safe fields only."""
    key = (code or "").strip()
    if not key:
        raise AcademicError(422, "code is required")
    school = (
        db.query(School)
        .filter(
            School.deleted_at.is_(None),
            School.code.isnot(None),
            func.lower(func.btrim(School.code)) == key.lower(),
        )
        .first()
    )
    if school is None:
        raise AcademicError(404, "School not found")
    payload = _public_payload(school)
    # For code lookup, surface the public code (not admin secrets).
    payload["code"] = school.code
    return payload
