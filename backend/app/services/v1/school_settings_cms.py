"""School Admin settings CMS — content, FAQ, leave, exam terms, email, secrets, forms, contact, tickets.

HTML bodies are lightly scrubbed of ``<script>`` tags only (not a full HTML sanitizer).
"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import (
    ContactInquiry,
    Leave,
    LeaveType,
    School,
    SchoolContentPage,
    SchoolEmailTemplate,
    SchoolFaq,
    SchoolFormField,
    SchoolIntegrationSecret,
    SchoolLeaveSetting,
    SchoolOnlineExamTerms,
    SupportTicket,
    SupportTicketMessage,
)
from app.services.v1 import school_secrets_crypto as secrets_crypto
from app.services.v1.school_academics import (
    AcademicError,
    _commit,
    _envelope,
    _now,
    _owned,
    _page,
)

CONTENT_SLUGS = frozenset(
    {
        "privacy_policy",
        "terms_condition",
        "refund_cancellation",
        "contact_us",
        "about_us",
    }
)
WEB_CONTENT_SLUG = "web_content"

FORM_ENTITY_TYPES = frozenset({"student", "staff", "parent", "user"})
FORM_FIELD_TYPES = frozenset({"text", "number", "date", "select", "boolean"})

PROVIDER_WHATSAPP = "whatsapp_meta"
PROVIDER_FEE_GATEWAY = "fee_payment_gateway"

CONTACT_STATUSES = frozenset({"new", "read", "replied", "closed", "spam"})
TICKET_STATUSES = frozenset({"open", "pending", "resolved", "closed"})
TICKET_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})

# Strip script tags only — not a full HTML sanitizer (document in module docstring).
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)

_WRITE_BLOCKLIST = frozenset(
    {
        "school_id",
        "id",
        "deleted_at",
        "created_at",
        "updated_at",
        "secret_ciphertext",
    }
)


def sanitize_body(body: dict) -> dict:
    return {k: v for k, v in body.items() if k not in _WRITE_BLOCKLIST}


def _strip_scripts(html: str | None) -> str:
    if html is None:
        return ""
    return _SCRIPT_RE.sub("", str(html))


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _parse_json(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


# ---- Content pages ----


def _content_item(row: SchoolContentPage) -> dict:
    return {
        "id": row.id,
        "slug": row.slug,
        "title": row.title,
        "body": row.body or "",
        "updated_at": _iso(row.updated_at),
        "created_at": _iso(row.created_at),
    }


def _assert_content_slug(slug: str) -> str:
    key = (slug or "").strip()
    if key not in CONTENT_SLUGS:
        raise AcademicError(422, f"Unknown content slug: {slug}")
    return key


def get_content(db: Session, school_id: int, slug: str) -> dict:
    key = _assert_content_slug(slug)
    row = db.scalar(
        select(SchoolContentPage).where(
            SchoolContentPage.school_id == school_id,
            SchoolContentPage.slug == key,
            SchoolContentPage.deleted_at.is_(None),
        )
    )
    if row is None:
        return {"slug": key, "title": "", "body": "", "updated_at": None, "created_at": None, "id": None}
    return _content_item(row)


def put_content(db: Session, school_id: int, slug: str, body: dict) -> dict:
    key = _assert_content_slug(slug)
    data = sanitize_body(body)
    title = str(data.get("title") or "").strip()[:255]
    html = _strip_scripts(data.get("body") if data.get("body") is not None else "")
    if len(html) > 100_000:
        raise AcademicError(422, "Body exceeds maximum length")
    row = db.scalar(
        select(SchoolContentPage).where(
            SchoolContentPage.school_id == school_id,
            SchoolContentPage.slug == key,
            SchoolContentPage.deleted_at.is_(None),
        )
    )
    now = _now()
    if row is None:
        row = SchoolContentPage(
            school_id=school_id,
            slug=key,
            title=title or key.replace("_", " ").title(),
            body=html,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        if "title" in data:
            row.title = title or row.title
        if "body" in data or data.get("body") is not None:
            row.body = html
        row.updated_at = now
    _commit(db)
    db.refresh(row)
    return _content_item(row)


def get_web_content(db: Session, school_id: int) -> dict:
    row = db.scalar(
        select(SchoolContentPage).where(
            SchoolContentPage.school_id == school_id,
            SchoolContentPage.slug == WEB_CONTENT_SLUG,
            SchoolContentPage.deleted_at.is_(None),
        )
    )
    if row is None:
        return {
            "slug": WEB_CONTENT_SLUG,
            "title": "",
            "body": "",
            "updated_at": None,
            "created_at": None,
            "id": None,
        }
    return _content_item(row)


def put_web_content(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_body(body)
    title = str(data.get("title") or "").strip()[:255]
    html = _strip_scripts(data.get("body") if data.get("body") is not None else "")
    if len(html) > 100_000:
        raise AcademicError(422, "Body exceeds maximum length")
    row = db.scalar(
        select(SchoolContentPage).where(
            SchoolContentPage.school_id == school_id,
            SchoolContentPage.slug == WEB_CONTENT_SLUG,
            SchoolContentPage.deleted_at.is_(None),
        )
    )
    now = _now()
    if row is None:
        row = SchoolContentPage(
            school_id=school_id,
            slug=WEB_CONTENT_SLUG,
            title=title or "Web content",
            body=html,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        if "title" in data:
            row.title = title or row.title
        if "body" in data or data.get("body") is not None:
            row.body = html
        row.updated_at = now
    _commit(db)
    db.refresh(row)
    return _content_item(row)


# ---- FAQs ----


def _faq_item(row: SchoolFaq) -> dict:
    return {
        "id": row.id,
        "question": row.question,
        "answer": row.answer or "",
        "sort_order": row.sort_order,
        "status": row.status,
        "updated_at": _iso(row.updated_at),
        "created_at": _iso(row.created_at),
    }


def list_faqs(db: Session, school_id: int, *, page: int = 1, page_size: int = 20) -> dict:
    page, page_size = _page(page, page_size)
    base = select(SchoolFaq).where(SchoolFaq.school_id == school_id, SchoolFaq.deleted_at.is_(None))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(SchoolFaq.sort_order.asc(), SchoolFaq.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return _envelope([_faq_item(r) for r in rows], total, page, page_size)


def create_faq(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_body(body)
    question = str(data.get("question") or "").strip()
    if not question:
        raise AcademicError(422, "question is required")
    answer = _strip_scripts(data.get("answer") if data.get("answer") is not None else "")
    now = _now()
    row = SchoolFaq(
        school_id=school_id,
        question=question[:512],
        answer=answer,
        sort_order=int(data.get("sort_order") or 0),
        status=int(data.get("status") if data.get("status") is not None else 1),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _faq_item(row)


def update_faq(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, SchoolFaq, row_id, school_id)
    data = sanitize_body(body)
    if "question" in data:
        q = str(data.get("question") or "").strip()
        if not q:
            raise AcademicError(422, "question is required")
        row.question = q[:512]
    if "answer" in data:
        row.answer = _strip_scripts(data.get("answer"))
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = int(data["sort_order"])
    if "status" in data and data["status"] is not None:
        row.status = int(data["status"])
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _faq_item(row)


def soft_delete_faq(db: Session, school_id: int, row_id: int) -> dict:
    row = _owned(db, SchoolFaq, row_id, school_id)
    row.deleted_at = _now()
    row.updated_at = row.deleted_at
    _commit(db)
    return {"ok": True, "id": row_id}


# ---- Leave settings ----


def _leave_item(row: SchoolLeaveSetting | None) -> dict:
    if row is None:
        return {"id": None, "policy": None, "notes": None, "updated_at": None}
    return {
        "id": row.id,
        "policy": _parse_json(row.policy_json),
        "notes": row.notes,
        "updated_at": _iso(row.updated_at),
    }


def get_leave_settings(db: Session, school_id: int) -> dict:
    row = db.scalar(
        select(SchoolLeaveSetting).where(
            SchoolLeaveSetting.school_id == school_id,
            SchoolLeaveSetting.deleted_at.is_(None),
        )
    )
    return _leave_item(row)


def put_leave_settings(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_body(body)
    # Opaque policy document only — no accrual/approval math invented here.
    policy = data.get("policy")
    if policy is not None and not isinstance(policy, (dict, list)):
        raise AcademicError(422, "policy must be an object or array")
    notes = data.get("notes")
    row = db.scalar(
        select(SchoolLeaveSetting).where(
            SchoolLeaveSetting.school_id == school_id,
            SchoolLeaveSetting.deleted_at.is_(None),
        )
    )
    now = _now()
    policy_json = json.dumps(policy) if policy is not None else None
    if row is None:
        row = SchoolLeaveSetting(
            school_id=school_id,
            policy_json=policy_json if "policy" in data else None,
            notes=str(notes) if notes is not None else None,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        if "policy" in data:
            row.policy_json = policy_json
        if "notes" in data:
            row.notes = None if notes is None else str(notes)
        row.updated_at = now
    if "policy" in data and isinstance(policy, dict):
        _maybe_seed_leave_types_from_policy(db, school_id, policy)
    _commit(db)
    db.refresh(row)
    return _leave_item(row)


# ---- Leave types (first-class) ----


def _leave_type_item(row: LeaveType) -> dict:
    return {
        "id": row.id,
        "code": row.code,
        "name": row.name,
        "description": row.description,
        "is_paid": bool(row.is_paid),
        "days_per_year": row.days_per_year,
        "applies_to": row.applies_to or "all",
        "is_active": bool(row.is_active),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _maybe_seed_leave_types_from_policy(db: Session, school_id: int, policy: dict) -> None:
    """Best-effort migrate policy.types[] into leave_types rows; never delete policy JSON."""
    types = policy.get("types")
    if not isinstance(types, list):
        return
    now = _now()
    for raw in types:
        if not isinstance(raw, dict):
            continue
        code = str(raw.get("key") or raw.get("code") or "").strip()
        name = str(raw.get("name") or code).strip()
        if not code or not name:
            continue
        existing = db.scalar(
            select(LeaveType).where(
                LeaveType.school_id == school_id,
                LeaveType.code == code,
                LeaveType.deleted_at.is_(None),
            )
        )
        if existing is not None:
            continue
        days = raw.get("days_per_year")
        db.add(
            LeaveType(
                school_id=school_id,
                code=code[:64],
                name=name[:128],
                description=raw.get("description"),
                is_paid=1 if raw.get("is_paid", True) else 0,
                days_per_year=int(days) if days is not None else None,
                applies_to=str(raw.get("applies_to") or "all")[:64],
                is_active=1,
                created_at=now,
                updated_at=now,
            )
        )


def list_leave_types(
    db: Session,
    school_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    active_only: bool = False,
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(LeaveType).filter(
        LeaveType.school_id == school_id,
        LeaveType.deleted_at.is_(None),
    )
    if active_only:
        query = query.filter(LeaveType.is_active == 1)
    total = query.count()
    rows = query.order_by(LeaveType.name.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_leave_type_item(r) for r in rows], total, page, page_size)


def get_leave_type(db: Session, school_id: int, row_id: int) -> dict:
    return _leave_type_item(_owned(db, LeaveType, row_id, school_id))


def create_leave_type(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_body(body)
    code = str(data.get("code") or data.get("key") or "").strip()
    name = str(data.get("name") or "").strip()
    if not code or not name:
        raise AcademicError(422, "code and name are required")
    dup = db.scalar(
        select(LeaveType).where(
            LeaveType.school_id == school_id,
            LeaveType.code == code,
            LeaveType.deleted_at.is_(None),
        )
    )
    if dup is not None:
        raise AcademicError(409, "Leave type code already exists")
    now = _now()
    days = data.get("days_per_year")
    row = LeaveType(
        school_id=school_id,
        code=code[:64],
        name=name[:128],
        description=data.get("description"),
        is_paid=1 if data.get("is_paid", True) else 0,
        days_per_year=int(days) if days is not None else None,
        applies_to=str(data.get("applies_to") or "all")[:64],
        is_active=1 if data.get("is_active", True) else 0,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _leave_type_item(row)


def update_leave_type(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, LeaveType, row_id, school_id)
    data = sanitize_body(body)
    if "code" in data and data["code"] is not None:
        code = str(data["code"]).strip()
        if not code:
            raise AcademicError(422, "code is required")
        dup = db.scalar(
            select(LeaveType).where(
                LeaveType.school_id == school_id,
                LeaveType.code == code,
                LeaveType.deleted_at.is_(None),
                LeaveType.id != row.id,
            )
        )
        if dup is not None:
            raise AcademicError(409, "Leave type code already exists")
        row.code = code[:64]
    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()
        if not name:
            raise AcademicError(422, "name is required")
        row.name = name[:128]
    if "description" in data:
        row.description = data["description"]
    if "is_paid" in data and data["is_paid"] is not None:
        row.is_paid = 1 if data["is_paid"] else 0
    if "days_per_year" in data:
        row.days_per_year = int(data["days_per_year"]) if data["days_per_year"] is not None else None
    if "applies_to" in data and data["applies_to"] is not None:
        row.applies_to = str(data["applies_to"])[:64]
    if "is_active" in data and data["is_active"] is not None:
        row.is_active = 1 if data["is_active"] else 0
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _leave_type_item(row)


def soft_delete_leave_type(db: Session, school_id: int, row_id: int) -> dict:
    row = _owned(db, LeaveType, row_id, school_id)
    row.deleted_at = _now()
    row.is_active = 0
    row.updated_at = row.deleted_at
    _commit(db)
    return {"ok": True, "id": row_id}


def list_leave_balances(
    db: Session,
    school_id: int,
    *,
    user_id: int | None = None,
    year: int | None = None,
) -> dict:
    """Simple derived balances: days_per_year − approved leave days in calendar year.

    No accrual engine. Pending leaves counted separately. Documented limitation.
    """
    from datetime import date as date_cls

    yr = int(year or date_cls.today().year)
    start = date_cls(yr, 1, 1)
    end = date_cls(yr, 12, 31)
    types = (
        db.query(LeaveType)
        .filter(
            LeaveType.school_id == school_id,
            LeaveType.deleted_at.is_(None),
            LeaveType.is_active == 1,
        )
        .order_by(LeaveType.name.asc())
        .all()
    )
    leave_q = db.query(Leave).filter(
        Leave.school_id == school_id,
        Leave.from_date <= end,
        Leave.to_date >= start,
    )
    if user_id is not None:
        leave_q = leave_q.filter(Leave.user_id == int(user_id))
    leaves = leave_q.all()

    def _overlap_days(row: Leave) -> int:
        a = max(row.from_date, start)
        b = min(row.to_date, end)
        if b < a:
            return 0
        return (b - a).days + 1

    items = []
    for lt in types:
        used = 0
        pending = 0
        for lv in leaves:
            if lv.leave_type_id is not None and lv.leave_type_id != lt.id:
                continue
            if lv.leave_type_id is None:
                # Match legacy "TypeName: reason" prefix when no FK.
                prefix = f"{lt.name}:"
                if not (lv.reason or "").startswith(prefix) and not (lv.reason or "").startswith(
                    f"{lt.code}:"
                ):
                    continue
            days = _overlap_days(lv)
            st = int(lv.status or 0)
            if st == 1:
                used += days
            elif st == 0:
                pending += days
            # status 2 rejected / 3 cancelled ignored
        allowed = lt.days_per_year
        remaining = None if allowed is None else max(0, int(allowed) - used)
        items.append(
            {
                "leave_type_id": lt.id,
                "leave_type": lt.name,
                "code": lt.code,
                "allowed": allowed,
                "used": used,
                "pending": pending,
                "remaining": remaining,
                "year": yr,
                "user_id": user_id,
            }
        )
    return {"items": items, "total": len(items), "year": yr, "user_id": user_id}


# ---- Online exam terms ----


def _exam_terms_item(row: SchoolOnlineExamTerms | None) -> dict:
    if row is None:
        return {"id": None, "title": "", "body": "", "updated_at": None}
    return {
        "id": row.id,
        "title": row.title or "",
        "body": row.body or "",
        "updated_at": _iso(row.updated_at),
    }


def get_online_exam_terms(db: Session, school_id: int) -> dict:
    row = db.scalar(
        select(SchoolOnlineExamTerms).where(
            SchoolOnlineExamTerms.school_id == school_id,
            SchoolOnlineExamTerms.deleted_at.is_(None),
        )
    )
    return _exam_terms_item(row)


def put_online_exam_terms(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_body(body)
    title = str(data.get("title") or "").strip()[:255]
    html = _strip_scripts(data.get("body") if data.get("body") is not None else "")
    row = db.scalar(
        select(SchoolOnlineExamTerms).where(
            SchoolOnlineExamTerms.school_id == school_id,
            SchoolOnlineExamTerms.deleted_at.is_(None),
        )
    )
    now = _now()
    if row is None:
        row = SchoolOnlineExamTerms(
            school_id=school_id,
            title=title,
            body=html,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        if "title" in data:
            row.title = title
        if "body" in data:
            row.body = html
        row.updated_at = now
    _commit(db)
    db.refresh(row)
    return _exam_terms_item(row)


# ---- Email templates ----


def _email_item(row: SchoolEmailTemplate) -> dict:
    return {
        "id": row.id,
        "key": row.key,
        "subject": row.subject,
        "body_text": row.body_text or "",
        "body_html": row.body_html,
        "locale": row.locale or "en",
        "updated_at": _iso(row.updated_at),
        "created_at": _iso(row.created_at),
    }


def list_email_templates(
    db: Session, school_id: int, *, page: int = 1, page_size: int = 20
) -> dict:
    page, page_size = _page(page, page_size)
    base = select(SchoolEmailTemplate).where(
        SchoolEmailTemplate.school_id == school_id,
        SchoolEmailTemplate.deleted_at.is_(None),
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(SchoolEmailTemplate.key.asc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return _envelope([_email_item(r) for r in rows], total, page, page_size)


def create_email_template(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_body(body)
    key = str(data.get("key") or "").strip()[:64]
    subject = str(data.get("subject") or "").strip()[:255]
    if not key or not subject:
        raise AcademicError(422, "key and subject are required")
    now = _now()
    row = SchoolEmailTemplate(
        school_id=school_id,
        key=key,
        subject=subject,
        body_text=str(data.get("body_text") or ""),
        body_html=_strip_scripts(data["body_html"]) if data.get("body_html") is not None else None,
        locale=str(data.get("locale") or "en")[:16],
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _email_item(row)


def get_email_template(db: Session, school_id: int, row_id: int) -> dict:
    return _email_item(_owned(db, SchoolEmailTemplate, row_id, school_id))


def update_email_template(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, SchoolEmailTemplate, row_id, school_id)
    data = sanitize_body(body)
    if "key" in data:
        key = str(data.get("key") or "").strip()[:64]
        if not key:
            raise AcademicError(422, "key is required")
        row.key = key
    if "subject" in data:
        subject = str(data.get("subject") or "").strip()[:255]
        if not subject:
            raise AcademicError(422, "subject is required")
        row.subject = subject
    if "body_text" in data:
        row.body_text = str(data.get("body_text") or "")
    if "body_html" in data:
        row.body_html = None if data["body_html"] is None else _strip_scripts(data["body_html"])
    if "locale" in data and data["locale"] is not None:
        row.locale = str(data["locale"])[:16]
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _email_item(row)


def soft_delete_email_template(db: Session, school_id: int, row_id: int) -> dict:
    row = _owned(db, SchoolEmailTemplate, row_id, school_id)
    row.deleted_at = _now()
    row.updated_at = row.deleted_at
    _commit(db)
    return {"ok": True, "id": row_id}


# ---- Integrations ----


def _integration_item(row: SchoolIntegrationSecret | None, provider: str) -> dict:
    if row is None:
        return {"provider": provider, "public_config": None, "configured": False, "updated_at": None}
    return {
        "provider": row.provider,
        "public_config": _parse_json(row.public_config_json),
        "configured": bool(row.secret_ciphertext),
        "updated_at": _iso(row.updated_at),
    }


def _get_integration(db: Session, school_id: int, provider: str) -> SchoolIntegrationSecret | None:
    return db.scalar(
        select(SchoolIntegrationSecret).where(
            SchoolIntegrationSecret.school_id == school_id,
            SchoolIntegrationSecret.provider == provider,
            SchoolIntegrationSecret.deleted_at.is_(None),
        )
    )


def _put_integration(db: Session, school_id: int, provider: str, body: dict) -> dict:
    data = sanitize_body(body)
    provider = (provider or "").strip()[:64]
    if not provider:
        raise AcademicError(422, "provider is required")
    public_config = data.get("public_config")
    if public_config is not None and not isinstance(public_config, dict):
        raise AcademicError(422, "public_config must be an object")
    secret = data.get("secret")
    clear_secret = bool(data.get("clear_secret"))
    row = _get_integration(db, school_id, provider)
    now = _now()
    ciphertext = None
    if secret is not None and str(secret) != "":
        # Encrypt before persist; never return plaintext.
        ciphertext = secrets_crypto.encrypt_secret(str(secret))
    if row is None:
        row = SchoolIntegrationSecret(
            school_id=school_id,
            provider=provider,
            public_config_json=json.dumps(public_config) if public_config is not None else None,
            secret_ciphertext=ciphertext,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        if "public_config" in data:
            row.public_config_json = json.dumps(public_config) if public_config is not None else None
        if clear_secret:
            row.secret_ciphertext = None
        elif ciphertext is not None:
            row.secret_ciphertext = ciphertext
        row.updated_at = now
    _commit(db)
    db.refresh(row)
    return _integration_item(row, provider)


def get_whatsapp_settings(db: Session, school_id: int) -> dict:
    return _integration_item(_get_integration(db, school_id, PROVIDER_WHATSAPP), PROVIDER_WHATSAPP)


def put_whatsapp_settings(db: Session, school_id: int, body: dict) -> dict:
    return _put_integration(db, school_id, PROVIDER_WHATSAPP, body)


def get_payment_gateway_settings(db: Session, school_id: int) -> dict:
    return _integration_item(
        _get_integration(db, school_id, PROVIDER_FEE_GATEWAY), PROVIDER_FEE_GATEWAY
    )


def put_payment_gateway_settings(db: Session, school_id: int, body: dict) -> dict:
    return _put_integration(db, school_id, PROVIDER_FEE_GATEWAY, body)


def list_third_party_integrations(db: Session, school_id: int) -> dict:
    rows = db.scalars(
        select(SchoolIntegrationSecret).where(
            SchoolIntegrationSecret.school_id == school_id,
            SchoolIntegrationSecret.deleted_at.is_(None),
            SchoolIntegrationSecret.provider.notin_([PROVIDER_WHATSAPP, PROVIDER_FEE_GATEWAY]),
        )
    ).all()
    items = [_integration_item(r, r.provider) for r in rows]
    return {"items": items, "total": len(items)}


def put_third_party_integration(db: Session, school_id: int, provider: str, body: dict) -> dict:
    key = (provider or "").strip()[:64]
    if key in {PROVIDER_WHATSAPP, PROVIDER_FEE_GATEWAY}:
        raise AcademicError(422, "Use the dedicated WhatsApp or payment-gateway endpoints")
    return _put_integration(db, school_id, key, body)


# ---- Form fields ----


def _form_field_item(row: SchoolFormField) -> dict:
    return {
        "id": row.id,
        "entity_type": row.entity_type,
        "field_key": row.field_key,
        "label": row.label,
        "field_type": row.field_type,
        "required": int(row.required or 0),
        "options": _parse_json(row.options_json),
        "sort_order": row.sort_order,
        "updated_at": _iso(row.updated_at),
        "created_at": _iso(row.created_at),
    }


def list_form_fields(
    db: Session,
    school_id: int,
    *,
    entity_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size = _page(page, page_size)
    q = select(SchoolFormField).where(
        SchoolFormField.school_id == school_id,
        SchoolFormField.deleted_at.is_(None),
    )
    if entity_type:
        et = entity_type.strip().lower()
        if et not in FORM_ENTITY_TYPES:
            raise AcademicError(422, f"Invalid entity_type: {entity_type}")
        q = q.where(SchoolFormField.entity_type == et)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(SchoolFormField.sort_order.asc(), SchoolFormField.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return _envelope([_form_field_item(r) for r in rows], total, page, page_size)


def create_form_field(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_body(body)
    entity_type = str(data.get("entity_type") or "").strip().lower()
    field_type = str(data.get("field_type") or "").strip().lower()
    field_key = str(data.get("field_key") or "").strip()[:64]
    label = str(data.get("label") or "").strip()[:255]
    if entity_type not in FORM_ENTITY_TYPES:
        raise AcademicError(422, f"Invalid entity_type: {entity_type}")
    if field_type not in FORM_FIELD_TYPES:
        raise AcademicError(422, f"Invalid field_type: {field_type}")
    if not field_key or not label:
        raise AcademicError(422, "field_key and label are required")
    options = data.get("options")
    if options is not None and not isinstance(options, (list, dict)):
        raise AcademicError(422, "options must be a list or object")
    now = _now()
    row = SchoolFormField(
        school_id=school_id,
        entity_type=entity_type,
        field_key=field_key,
        label=label,
        field_type=field_type,
        required=1 if data.get("required") in (1, True, "1", "true") else 0,
        options_json=json.dumps(options) if options is not None else None,
        sort_order=int(data.get("sort_order") or 0),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _form_field_item(row)


def update_form_field(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, SchoolFormField, row_id, school_id)
    data = sanitize_body(body)
    if "entity_type" in data:
        et = str(data.get("entity_type") or "").strip().lower()
        if et not in FORM_ENTITY_TYPES:
            raise AcademicError(422, f"Invalid entity_type: {et}")
        row.entity_type = et
    if "field_type" in data:
        ft = str(data.get("field_type") or "").strip().lower()
        if ft not in FORM_FIELD_TYPES:
            raise AcademicError(422, f"Invalid field_type: {ft}")
        row.field_type = ft
    if "field_key" in data:
        fk = str(data.get("field_key") or "").strip()[:64]
        if not fk:
            raise AcademicError(422, "field_key is required")
        row.field_key = fk
    if "label" in data:
        label = str(data.get("label") or "").strip()[:255]
        if not label:
            raise AcademicError(422, "label is required")
        row.label = label
    if "required" in data:
        row.required = 1 if data.get("required") in (1, True, "1", "true") else 0
    if "options" in data:
        options = data["options"]
        if options is not None and not isinstance(options, (list, dict)):
            raise AcademicError(422, "options must be a list or object")
        row.options_json = json.dumps(options) if options is not None else None
    if "sort_order" in data and data["sort_order"] is not None:
        row.sort_order = int(data["sort_order"])
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _form_field_item(row)


def soft_delete_form_field(db: Session, school_id: int, row_id: int) -> dict:
    row = _owned(db, SchoolFormField, row_id, school_id)
    row.deleted_at = _now()
    row.updated_at = row.deleted_at
    _commit(db)
    return {"ok": True, "id": row_id}


# ---- Contact inquiries ----


def _contact_item(row: ContactInquiry) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "email": row.email,
        "phone": row.phone,
        "subject": row.subject,
        "message": row.message,
        "status": row.status,
        "source": row.source,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def list_contact_inquiries(
    db: Session,
    school_id: int,
    *,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size = _page(page, page_size)
    q = select(ContactInquiry).where(
        ContactInquiry.school_id == school_id,
        ContactInquiry.deleted_at.is_(None),
    )
    if status_filter:
        q = q.where(ContactInquiry.status == status_filter.strip())
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(ContactInquiry.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return _envelope([_contact_item(r) for r in rows], total, page, page_size)


def get_contact_inquiry(db: Session, school_id: int, row_id: int) -> dict:
    return _contact_item(_owned(db, ContactInquiry, row_id, school_id))


def patch_contact_inquiry(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, ContactInquiry, row_id, school_id)
    data = sanitize_body(body)
    if "status" in data:
        status_val = str(data.get("status") or "").strip()
        if status_val not in CONTACT_STATUSES:
            raise AcademicError(422, f"Invalid status: {status_val}")
        row.status = status_val
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _contact_item(row)


def create_contact_inquiry_for_school(
    db: Session,
    school_id: int,
    body: dict,
    *,
    source: str = "school_admin",
) -> dict:
    data = sanitize_body(body)
    name = str(data.get("name") or "").strip()[:255]
    email = str(data.get("email") or "").strip()[:255]
    subject = str(data.get("subject") or "").strip()[:255]
    message = str(data.get("message") or "").strip()
    if not name or not email or not subject or not message:
        raise AcademicError(422, "name, email, subject and message are required")
    now = _now()
    row = ContactInquiry(
        school_id=school_id,
        name=name,
        email=email,
        phone=(str(data["phone"]).strip()[:64] if data.get("phone") else None),
        subject=subject,
        message=message,
        status="new",
        source=(source or "school_admin")[:64],
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _contact_item(row)


def resolve_school_by_code(db: Session, code: str) -> School:
    key = (code or "").strip()
    if not key:
        raise AcademicError(404, "School not found")
    school = db.scalar(
        select(School).where(
            School.code == key,
            School.deleted_at.is_(None),
            School.status == 1,
        )
    )
    if school is None:
        raise AcademicError(404, "School not found")
    return school


def create_public_contact_inquiry(db: Session, code: str, body: dict) -> dict:
    school = resolve_school_by_code(db, code)
    # Never accept school_id from body — ownership resolved via school code only.
    return create_contact_inquiry_for_school(db, school.id, body, source="public")


# ---- Support tickets ----


def _ticket_item(row: SupportTicket, *, messages: list[dict] | None = None) -> dict:
    payload = {
        "id": row.id,
        "subject": row.subject,
        "body": row.body,
        "status": row.status,
        "priority": row.priority,
        "opener_type": row.opener_type,
        "opener_ref": row.opener_ref,
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }
    if messages is not None:
        payload["messages"] = messages
    return payload


def _message_item(row: SupportTicketMessage) -> dict:
    return {
        "id": row.id,
        "ticket_id": row.ticket_id,
        "author_type": row.author_type,
        "author_ref": row.author_ref,
        "body": row.body,
        "created_at": _iso(row.created_at),
    }


def list_support_tickets(
    db: Session,
    school_id: int,
    *,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page, page_size = _page(page, page_size)
    q = select(SupportTicket).where(
        SupportTicket.school_id == school_id,
        SupportTicket.deleted_at.is_(None),
    )
    if status_filter:
        q = q.where(SupportTicket.status == status_filter.strip())
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(SupportTicket.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return _envelope([_ticket_item(r) for r in rows], total, page, page_size)


def create_support_ticket(db: Session, school_id: int, body: dict) -> dict:
    data = sanitize_body(body)
    subject = str(data.get("subject") or "").strip()[:255]
    ticket_body = str(data.get("body") or "").strip()
    opener_type = str(data.get("opener_type") or "school_admin").strip()[:32]
    if not subject or not ticket_body:
        raise AcademicError(422, "subject and body are required")
    priority = str(data.get("priority") or "normal").strip()
    if priority not in TICKET_PRIORITIES:
        raise AcademicError(422, f"Invalid priority: {priority}")
    now = _now()
    row = SupportTicket(
        school_id=school_id,
        subject=subject,
        body=ticket_body,
        status="open",
        priority=priority,
        opener_type=opener_type,
        opener_ref=(str(data["opener_ref"])[:64] if data.get("opener_ref") else None),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _ticket_item(row)


def get_support_ticket(db: Session, school_id: int, row_id: int) -> dict:
    row = _owned(db, SupportTicket, row_id, school_id)
    msgs = db.scalars(
        select(SupportTicketMessage)
        .where(
            SupportTicketMessage.school_id == school_id,
            SupportTicketMessage.ticket_id == row.id,
            SupportTicketMessage.deleted_at.is_(None),
        )
        .order_by(SupportTicketMessage.id.asc())
    ).all()
    return _ticket_item(row, messages=[_message_item(m) for m in msgs])


def patch_support_ticket(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, SupportTicket, row_id, school_id)
    data = sanitize_body(body)
    if "status" in data:
        status_val = str(data.get("status") or "").strip()
        if status_val not in TICKET_STATUSES:
            raise AcademicError(422, f"Invalid status: {status_val}")
        row.status = status_val
    if "priority" in data:
        priority = str(data.get("priority") or "").strip()
        if priority not in TICKET_PRIORITIES:
            raise AcademicError(422, f"Invalid priority: {priority}")
        row.priority = priority
    if "subject" in data:
        subject = str(data.get("subject") or "").strip()[:255]
        if not subject:
            raise AcademicError(422, "subject is required")
        row.subject = subject
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _ticket_item(row)


def add_support_ticket_message(
    db: Session, school_id: int, ticket_id: int, body: dict
) -> dict:
    ticket = _owned(db, SupportTicket, ticket_id, school_id)
    data = sanitize_body(body)
    text = str(data.get("body") or "").strip()
    if not text:
        raise AcademicError(422, "body is required")
    author_type = str(data.get("author_type") or "school_admin").strip()[:32]
    now = _now()
    row = SupportTicketMessage(
        school_id=school_id,
        ticket_id=ticket.id,
        author_type=author_type,
        author_ref=(str(data["author_ref"])[:64] if data.get("author_ref") else None),
        body=text,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    ticket.updated_at = now
    _commit(db)
    db.refresh(row)
    return _message_item(row)
