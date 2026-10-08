from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.v1.common import PaginatedResponse


class SettingsPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: dict[str, Optional[str]] = Field(min_length=1)


class SettingValueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Optional[str] = None
    secret: bool = False
    configured: bool = False
    type: Optional[str] = None


class SettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settings: dict[str, SettingValueResponse]
    updated_keys: list[str] = Field(default_factory=list)


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    school_id: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "AuditLogResponse":
        meta: dict[str, Any] = {}
        if row.metadata_json:
            try:
                parsed = json.loads(row.metadata_json)
                if isinstance(parsed, dict):
                    meta = parsed
            except json.JSONDecodeError:
                meta = {}
        return cls(
            id=row.id,
            actor_id=row.actor_id,
            actor_email=row.actor_email,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            school_id=row.school_id,
            metadata=meta,
            created_at=row.created_at,
        )


class AuditLogListResponse(PaginatedResponse):
    items: list[AuditLogResponse]


class NotificationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    body: Optional[str] = None
    school_id: Optional[int] = Field(default=None, ge=1)
    status: int = Field(default=0, ge=0, le=2)


class NotificationStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=2)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: Optional[str] = None
    status: int
    school_id: Optional[int] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NotificationListResponse(PaginatedResponse):
    items: list[NotificationResponse]
