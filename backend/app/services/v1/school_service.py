"""Super Admin school CRUD — reuses legacy School model (no duplicate table)."""

from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from urllib.parse import urlparse

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.tables import School

# Verified in FastAPI (mobile_auth / admin_data / school_is_ready):
# status=1 active; status=0 blocks mobile login.
# installed=1 required for school-code admin login / school_is_ready.
STATUS_ACTIVE = 1
STATUS_INACTIVE = 0
INSTALLED_YES = 1
INSTALLED_NO = 0

DOMAIN_TYPE_DEFAULT = "default"
DOMAIN_TYPE_CUSTOM = "custom"
DOMAIN_TYPES = frozenset({DOMAIN_TYPE_DEFAULT, DOMAIN_TYPE_CUSTOM})

# Subdomain label for domain_type=default (prefix only; stored domain is full host).
_SUBDOMAIN_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_HOSTNAME_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_RESERVED_SUBDOMAINS = frozenset(
    {
        "www",
        "api",
        "admin",
        "app",
        "mail",
        "ftp",
        "localhost",
        "staging",
        "static",
        "cdn",
    }
)


class SchoolServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


_EMAIL = TypeAdapter(EmailStr)


def normalize_support_email(value: str | None) -> str:
    """Blank stays blank. A non-blank value must be a valid email. Does not rewrite stored rows."""
    text = (value or "").strip()
    if not text:
        return ""
    try:
        return str(_EMAIL.validate_python(text))
    except ValidationError as exc:
        raise SchoolServiceError("Invalid support email", status_code=422) from exc


def normalize_school_website(value: str | None) -> str:
    """Blank stays blank. Non-blank must be http(s) URL with a hostname."""
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) > 512:
        raise SchoolServiceError("school_website must be at most 512 characters", status_code=422)
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or not parsed.hostname:
        raise SchoolServiceError(
            "school_website must be a valid http or https URL",
            status_code=422,
        )
    if parsed.username or parsed.password:
        raise SchoolServiceError("school_website must not include credentials", status_code=422)
    return text


def normalize_domain_type(value: str | None) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    cleaned = str(value).strip().lower()
    if cleaned not in DOMAIN_TYPES:
        raise SchoolServiceError(
            "domain_type must be 'default' or 'custom'",
            status_code=422,
        )
    return cleaned


def _normalize_hostname(value: str) -> str:
    host = (value or "").strip().lower().rstrip(".")
    if "://" in host or "/" in host or "?" in host or "#" in host or "@" in host or " " in host:
        raise SchoolServiceError("domain must be a hostname without scheme or path", status_code=422)
    if not host or len(host) > 253:
        raise SchoolServiceError("domain is invalid", status_code=422)
    if host[0] == "." or ".." in host:
        raise SchoolServiceError("domain is invalid", status_code=422)
    labels = host.split(".")
    if len(labels) < 2:
        raise SchoolServiceError("domain must be a fully-qualified hostname", status_code=422)
    for label in labels:
        if not _HOSTNAME_LABEL_RE.match(label):
            raise SchoolServiceError("domain contains an invalid hostname label", status_code=422)
    return host


def _normalize_subdomain_prefix(value: str) -> str:
    prefix = (value or "").strip().lower().rstrip(".")
    if not prefix:
        raise SchoolServiceError("domain subdomain prefix is required for default domains", status_code=422)
    if "." in prefix:
        raise SchoolServiceError(
            "default domain expects a subdomain prefix only (not a full hostname)",
            status_code=422,
        )
    if not _SUBDOMAIN_RE.match(prefix):
        raise SchoolServiceError(
            "domain subdomain prefix may only contain lowercase letters, digits, and hyphens",
            status_code=422,
        )
    if prefix in _RESERVED_SUBDOMAINS:
        raise SchoolServiceError("domain subdomain prefix is reserved", status_code=422)
    return prefix


def resolve_school_domain(
    *,
    domain: str | None,
    domain_type: str | None,
) -> tuple[str | None, str | None, int]:
    """Return (stored_hostname, domain_type, domain_verified).

    Stored ``schools.domain`` is always a full hostname when set.
    - domain_type=default: request ``domain`` is a subdomain prefix; constructed with
      ``Settings.resolved_school_base_domain``; verified=1 (platform-owned).
    - domain_type=custom: request ``domain`` is a full hostname; verified=0.
    - domain_type omitted (legacy): store ``domain`` as-is after light normalization when
      provided; verified=0. Does not rewrite existing clients that omit domain_type.
    """
    dtype = normalize_domain_type(domain_type)
    raw = (domain or "").strip() or None

    if dtype == DOMAIN_TYPE_DEFAULT:
        if not raw:
            raise SchoolServiceError("domain is required when domain_type is default", status_code=422)
        prefix = _normalize_subdomain_prefix(raw)
        base = get_settings().resolved_school_base_domain
        if not base:
            raise SchoolServiceError(
                "School base domain is not configured (set SCHOOL_BASE_DOMAIN or APP_URL)",
                status_code=500,
            )
        return f"{prefix}.{base}", DOMAIN_TYPE_DEFAULT, 1

    if dtype == DOMAIN_TYPE_CUSTOM:
        if not raw:
            raise SchoolServiceError("domain is required when domain_type is custom", status_code=422)
        return _normalize_hostname(raw), DOMAIN_TYPE_CUSTOM, 0

    # Legacy / omitted domain_type: preserve prior semantics (store provided string).
    if raw is None:
        return None, None, 0
    # Prefer FQDN validation when the value looks like a hostname with a dot.
    if "." in raw and "://" not in raw and "/" not in raw:
        return _normalize_hostname(raw), None, 0
    cleaned = raw.lower().rstrip(".")
    if not cleaned or len(cleaned) > 255:
        raise SchoolServiceError("domain is invalid", status_code=422)
    return cleaned, None, 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_code(code: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "", code.strip().upper())
    if not cleaned:
        raise SchoolServiceError("Invalid school code", status_code=422)
    return cleaned[:255]


def _generate_code(db: Session, name: str) -> str:
    base = _normalize_code(re.sub(r"\s+", "", name)[:12] or "SCH")
    for _ in range(20):
        candidate = f"{base}{secrets.token_hex(2).upper()}"
        exists = db.scalar(select(School.id).where(School.code == candidate))
        if exists is None:
            return candidate
    raise SchoolServiceError("Could not allocate unique school code", status_code=500)


def _ensure_code_available(db: Session, code: str, *, exclude_id: int | None = None) -> None:
    query = select(School.id).where(School.code == code)
    if exclude_id is not None:
        query = query.where(School.id != exclude_id)
    if db.scalar(query) is not None:
        raise SchoolServiceError("School code already in use", status_code=409)


def _ensure_email_available(db: Session, email: str, *, exclude_id: int | None = None) -> None:
    """Reject another school with the same non-blank email, ignoring case and surrounding space."""
    if not email:
        return
    query = select(School.id).where(
        func.lower(func.btrim(School.support_email)) == email.lower(),
        func.btrim(School.support_email) != "",
    )
    if exclude_id is not None:
        query = query.where(School.id != exclude_id)
    if db.scalar(query) is not None:
        raise SchoolServiceError("School email already in use", status_code=409)


def _ensure_domain_available(db: Session, domain: str | None, *, exclude_id: int | None = None) -> None:
    if not domain:
        return
    query = select(School.id).where(
        func.lower(func.btrim(School.domain)) == domain.lower(),
        School.domain.is_not(None),
        func.btrim(School.domain) != "",
    )
    if exclude_id is not None:
        query = query.where(School.id != exclude_id)
    if db.scalar(query) is not None:
        raise SchoolServiceError("School domain already in use", status_code=409)


def _commit_school(db: Session) -> None:
    """Commit, mapping the non-blank email unique index to the same 409 as the pre-check."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        message = str(getattr(exc, "orig", exc)).lower()
        if "ix_schools_support_email_nonblank" in message:
            raise SchoolServiceError("School email already in use", status_code=409) from exc
        if "ix_schools_domain_nonblank" in message:
            raise SchoolServiceError("School domain already in use", status_code=409) from exc
        if "ix_schools_code" in message or "schools_code_key" in message:
            raise SchoolServiceError("School code already in use", status_code=409) from exc
        raise


def get_school(db: Session, school_id: int, *, include_deleted: bool = False) -> School:
    school = db.get(School, school_id)
    if school is None or (not include_deleted and school.deleted_at is not None):
        raise SchoolServiceError("School not found", status_code=404)
    return school


def create_school(
    db: Session,
    *,
    name: str,
    address: str = "",
    support_phone: str = "",
    support_email: str = "",
    tagline: str = "",
    logo: str = "",
    code: str | None = None,
    domain: str | None = None,
    domain_type: str | None = None,
    school_website: str = "",
    status: int = STATUS_ACTIVE,
    installed: int = INSTALLED_YES,
    commit: bool = True,
) -> School:
    if status not in (STATUS_ACTIVE, STATUS_INACTIVE):
        raise SchoolServiceError("Invalid status", status_code=422)
    if installed not in (INSTALLED_YES, INSTALLED_NO):
        raise SchoolServiceError("Invalid installed flag", status_code=422)
    now = _utcnow()
    if code:
        normalized = _normalize_code(code)
        _ensure_code_available(db, normalized)
    else:
        normalized = _generate_code(db, name)
    email = normalize_support_email(support_email)
    _ensure_email_available(db, email)
    website = normalize_school_website(school_website)
    stored_domain, stored_type, domain_verified = resolve_school_domain(
        domain=domain, domain_type=domain_type
    )
    _ensure_domain_available(db, stored_domain)

    school = School(
        name=name.strip(),
        address=address or "",
        support_phone=support_phone or "",
        support_email=email,
        tagline=tagline or "",
        logo=logo or "",
        code=normalized,
        domain=stored_domain,
        domain_type=stored_type,
        domain_verified=domain_verified,
        school_website=website,
        status=status,
        installed=installed,
        admin_id=None,
        database_name=None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(school)
    if commit:
        _commit_school(db)
        db.refresh(school)
    else:
        db.flush()
    return school


_SCHOOL_SORTS = {
    "name": (School.name.asc(), School.id.asc()),
    "-name": (School.name.desc(), School.id.desc()),
    "created_at": (School.created_at.asc().nulls_last(), School.id.asc()),
    "-created_at": (School.created_at.desc().nulls_last(), School.id.desc()),
}


def list_schools(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
    code: str | None = None,
    name: str | None = None,
    support_email: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    include_deleted: bool = False,
) -> tuple[list[School], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = select(School)
    count_query = select(func.count()).select_from(School)

    if not include_deleted:
        query = query.where(School.deleted_at.is_(None))
        count_query = count_query.where(School.deleted_at.is_(None))
    if status is not None:
        if status not in (STATUS_INACTIVE, STATUS_ACTIVE):
            raise SchoolServiceError("Invalid status", status_code=422)
        query = query.where(School.status == status)
        count_query = count_query.where(School.status == status)
    if code:
        query = query.where(School.code == _normalize_code(code))
        count_query = count_query.where(School.code == _normalize_code(code))
    if name:
        like = f"%{name.strip()}%"
        query = query.where(School.name.ilike(like))
        count_query = count_query.where(School.name.ilike(like))
    if support_email:
        like = f"%{support_email.strip()}%"
        query = query.where(School.support_email.ilike(like))
        count_query = count_query.where(School.support_email.ilike(like))
    if q and q.strip():
        like = f"%{q.strip()}%"
        search = or_(School.name.ilike(like), School.code.ilike(like))
        query = query.where(search)
        count_query = count_query.where(search)

    sort_key = (sort or "").strip()
    if not sort_key:
        ordering = (School.id.desc(),)
    elif sort_key not in _SCHOOL_SORTS:
        raise SchoolServiceError("Invalid sort", status_code=422)
    else:
        ordering = _SCHOOL_SORTS[sort_key]

    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(query.order_by(*ordering).offset((page - 1) * page_size).limit(page_size))
    )
    return rows, total


def update_school(
    db: Session,
    school_id: int,
    *,
    name: str | None = None,
    address: str | None = None,
    support_phone: str | None = None,
    support_email: str | None = None,
    tagline: str | None = None,
    logo: str | None = None,
    code: str | None = None,
    domain: str | None = None,
    domain_type: str | None = None,
    school_website: str | None = None,
    domain_set: bool = False,
    domain_type_set: bool = False,
) -> School:
    school = get_school(db, school_id)
    if name is not None:
        school.name = name.strip()
    if address is not None:
        school.address = address
    if support_phone is not None:
        school.support_phone = support_phone
    if support_email is not None:
        email = normalize_support_email(support_email)
        _ensure_email_available(db, email, exclude_id=school.id)
        school.support_email = email
    if tagline is not None:
        school.tagline = tagline
    if logo is not None:
        school.logo = logo
    if code is not None:
        normalized = _normalize_code(code)
        _ensure_code_available(db, normalized, exclude_id=school.id)
        school.code = normalized
    if school_website is not None:
        school.school_website = normalize_school_website(school_website)

    if domain_set or domain_type_set:
        clearing_domain = domain_set and (domain is None or str(domain).strip() == "")
        if clearing_domain:
            school.domain = None
            school.domain_type = (
                normalize_domain_type(domain_type) if domain_type_set else None
            )
            school.domain_verified = 0
        elif domain_type_set and not domain_set:
            # Changing type alone cannot safely reinterpret a stored FQDN as a prefix.
            raise SchoolServiceError(
                "domain is required when changing domain_type",
                status_code=422,
            )
        else:
            # domain_set with a non-empty value; domain_type may be omitted (keep current).
            resolve_type = domain_type if domain_type_set else school.domain_type
            stored_domain, stored_type, domain_verified = resolve_school_domain(
                domain=domain,
                domain_type=resolve_type,
            )
            _ensure_domain_available(db, stored_domain, exclude_id=school.id)
            school.domain = stored_domain
            school.domain_type = stored_type
            school.domain_verified = domain_verified

    school.updated_at = _utcnow()
    _commit_school(db)
    db.refresh(school)
    return school


def soft_delete_school(db: Session, school_id: int) -> School:
    school = get_school(db, school_id)
    school.deleted_at = _utcnow()
    school.updated_at = school.deleted_at
    db.commit()
    db.refresh(school)
    return school


def activate_school(db: Session, school_id: int) -> School:
    school = get_school(db, school_id)
    school.status = STATUS_ACTIVE
    school.installed = INSTALLED_YES
    school.updated_at = _utcnow()
    db.commit()
    db.refresh(school)
    return school


def suspend_school(db: Session, school_id: int) -> School:
    """status=0 — blocks mobile login (verified in mobile_auth)."""
    school = get_school(db, school_id)
    school.status = STATUS_INACTIVE
    school.updated_at = _utcnow()
    db.commit()
    db.refresh(school)
    return school


def deactivate_school(db: Session, school_id: int) -> School:
    """status=0 and installed=0 — blocks mobile + school-code admin readiness."""
    school = get_school(db, school_id)
    school.status = STATUS_INACTIVE
    school.installed = INSTALLED_NO
    school.updated_at = _utcnow()
    db.commit()
    db.refresh(school)
    return school


def provision_school(db: Session, school_id: int) -> tuple[School, bool]:
    """Idempotent shared-Neon provisioning (no physical DB create).

    Ensures school is active/installed and has a default session year.
    Returns (school, created_fresh) where created_fresh is True only on first provision.
    """
    from datetime import date

    from app.models.tables import SessionYear

    school = get_school(db, school_id)
    first_time = school.provisioned_at is None
    now = _utcnow()

    school.status = STATUS_ACTIVE
    school.installed = INSTALLED_YES
    if first_time:
        school.provisioned_at = now
    school.updated_at = now

    year = db.scalar(
        select(SessionYear).where(
            SessionYear.school_id == school.id,
            SessionYear.default == 1,
            SessionYear.deleted_at.is_(None),
        )
    )
    if year is None:
        y = now.year
        db.add(
            SessionYear(
                name=str(y),
                default=1,
                start_date=date(y, 1, 1),
                end_date=date(y, 12, 31),
                school_id=school.id,
                created_at=now,
                updated_at=now,
            )
        )

    db.commit()
    db.refresh(school)
    return school, first_time
