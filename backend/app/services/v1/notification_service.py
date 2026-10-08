"""Platform notifications for Super Admin (Phase 8). No external delivery."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.tables import Notification, School

STATUS_DRAFT = 0
STATUS_ACTIVE = 1
STATUS_ARCHIVED = 2
STATUSES = frozenset({STATUS_DRAFT, STATUS_ACTIVE, STATUS_ARCHIVED})


class NotificationServiceError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_notification(
    db: Session,
    *,
    title: str,
    body: str | None,
    school_id: int | None,
    created_by: UUID | None,
    status: int = STATUS_DRAFT,
) -> Notification:
    cleaned = title.strip()
    if not cleaned:
        raise NotificationServiceError("title is required", status_code=422)
    if status not in STATUSES:
        raise NotificationServiceError("Invalid status", status_code=422)
    if school_id is not None:
        school = db.get(School, school_id)
        if school is None or school.deleted_at is not None:
            raise NotificationServiceError("School not found", status_code=404)
    now = _utcnow()
    row = Notification(
        title=cleaned[:255],
        body=body,
        status=status,
        school_id=school_id,
        created_by=str(created_by) if created_by else None,
        deleted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_notifications(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
    school_id: int | None = None,
) -> tuple[list[Notification], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    query = select(Notification).where(Notification.deleted_at.is_(None))
    count_query = (
        select(func.count()).select_from(Notification).where(Notification.deleted_at.is_(None))
    )
    if status is not None:
        query = query.where(Notification.status == status)
        count_query = count_query.where(Notification.status == status)
    if school_id is not None:
        query = query.where(Notification.school_id == school_id)
        count_query = count_query.where(Notification.school_id == school_id)
    total = int(db.scalar(count_query) or 0)
    rows = list(
        db.scalars(
            query.order_by(Notification.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    )
    return rows, total


def get_notification(db: Session, notification_id: int) -> Notification:
    row = db.get(Notification, notification_id)
    if row is None or row.deleted_at is not None:
        raise NotificationServiceError("Notification not found", status_code=404)
    return row


def set_notification_status(db: Session, notification_id: int, *, status: int) -> Notification:
    if status not in STATUSES:
        raise NotificationServiceError("Invalid status", status_code=422)
    row = get_notification(db, notification_id)
    row.status = status
    row.updated_at = _utcnow()
    db.commit()
    db.refresh(row)
    return row
