"""Immutable Super Admin audit log writer + listing (Phase 8)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import AuditLog
from app.models.v1.user import User

_SECRET_KEY_RE = re.compile(
    r"(password|passwd|secret|token|api[_-]?key|private[_-]?key|authorization|credential)",
    re.IGNORECASE,
)


class AuditServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Strip secret-looking keys/values from audit metadata."""
    if not metadata:
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if _SECRET_KEY_RE.search(str(key)):
            continue
        if isinstance(value, str) and _SECRET_KEY_RE.search(value) and len(value) > 20:
            cleaned[key] = "[redacted]"
            continue
        if isinstance(value, dict):
            cleaned[key] = sanitize_metadata(value)
            continue
        cleaned[key] = value
    return cleaned


def record_audit(
    db: Session,
    *,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | int | UUID | None = None,
    school_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Persist an audit row. Caller must commit (or we commit with the surrounding txn)."""
    safe = sanitize_metadata(metadata)
    row = AuditLog(
        actor_id=str(actor.id) if actor is not None else None,
        actor_email=actor.email if actor is not None else None,
        action=action[:128],
        entity_type=entity_type[:64],
        entity_id=str(entity_id)[:64] if entity_id is not None else None,
        school_id=school_id,
        metadata_json=json.dumps(safe, default=str) if safe else None,
        created_at=_utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_audit_logs(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    entity_type: str | None = None,
    school_id: int | None = None,
    actor_id: str | None = None,
) -> tuple[list[AuditLog], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = select(AuditLog)
    count_query = select(func.count()).select_from(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if school_id is not None:
        query = query.where(AuditLog.school_id == school_id)
        count_query = count_query.where(AuditLog.school_id == school_id)
    if actor_id:
        query = query.where(AuditLog.actor_id == actor_id)
        count_query = count_query.where(AuditLog.actor_id == actor_id)
    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(
            query.order_by(AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    )
    return rows, total
