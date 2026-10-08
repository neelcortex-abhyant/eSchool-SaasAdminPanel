"""Platform notifications — /api/v1/super-admin/notifications."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.platform import (
    NotificationCreateRequest,
    NotificationListResponse,
    NotificationResponse,
    NotificationStatusRequest,
)
from app.services.v1 import audit_service, notification_service

router = APIRouter(prefix="/notifications", tags=["v1-super-admin-notifications"])


def _http(exc: notification_service.NotificationServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def create_notification(
    body: NotificationCreateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> NotificationResponse:
    try:
        row = notification_service.create_notification(
            db,
            title=body.title,
            body=body.body,
            school_id=body.school_id,
            created_by=auth.user.id,
            status=body.status,
        )
    except notification_service.NotificationServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db,
        actor=auth.user,
        action="notification.create",
        entity_type="notification",
        entity_id=row.id,
        school_id=row.school_id,
        metadata={"title": row.title, "status": row.status},
    )
    return NotificationResponse.model_validate(row)


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: int | None = Query(default=None, alias="status"),
    school_id: int | None = Query(default=None, ge=1),
) -> NotificationListResponse:
    try:
        rows, total = notification_service.list_notifications(
            db, page=page, page_size=page_size, status=status_filter, school_id=school_id
        )
    except notification_service.NotificationServiceError as exc:
        raise _http(exc) from exc
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification(
    notification_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> NotificationResponse:
    try:
        row = notification_service.get_notification(db, notification_id)
    except notification_service.NotificationServiceError as exc:
        raise _http(exc) from exc
    return NotificationResponse.model_validate(row)


@router.patch("/{notification_id}/status", response_model=NotificationResponse)
def patch_notification_status(
    notification_id: int,
    body: NotificationStatusRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> NotificationResponse:
    try:
        row = notification_service.set_notification_status(
            db, notification_id, status=body.status
        )
    except notification_service.NotificationServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db,
        actor=auth.user,
        action="notification.status",
        entity_type="notification",
        entity_id=row.id,
        school_id=row.school_id,
        metadata={"status": row.status},
    )
    return NotificationResponse.model_validate(row)
