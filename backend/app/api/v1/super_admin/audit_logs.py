"""Audit log listing — /api/v1/super-admin/audit-logs (read-only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.platform import AuditLogListResponse, AuditLogResponse
from app.services.v1 import audit_service

router = APIRouter(prefix="/audit-logs", tags=["v1-super-admin-audit-logs"])


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    school_id: int | None = Query(default=None, ge=1),
    actor_id: str | None = Query(default=None),
) -> AuditLogListResponse:
    rows, total = audit_service.list_audit_logs(
        db,
        page=page,
        page_size=page_size,
        action=action,
        entity_type=entity_type,
        school_id=school_id,
        actor_id=actor_id,
    )
    return AuditLogListResponse(
        items=[AuditLogResponse.from_row(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )
