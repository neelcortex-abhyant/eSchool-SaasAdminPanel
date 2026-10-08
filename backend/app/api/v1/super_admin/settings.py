"""Platform settings — /api/v1/super-admin/settings (reuses system_settings)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.platform import SettingValueResponse, SettingsPatchRequest, SettingsResponse
from app.services.v1 import audit_service, settings_service

router = APIRouter(prefix="/settings", tags=["v1-super-admin-settings"])


@router.get("", response_model=SettingsResponse)
def get_settings(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SettingsResponse:
    raw = settings_service.get_platform_settings(db)
    return SettingsResponse(
        settings={k: SettingValueResponse(**v) for k, v in raw["settings"].items()},
    )


@router.patch("", response_model=SettingsResponse)
def patch_settings(
    body: SettingsPatchRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SettingsResponse:
    try:
        raw = settings_service.update_platform_settings(db, body.settings)
    except settings_service.SettingsServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    audit_service.record_audit(
        db,
        actor=auth.user,
        action="settings.update",
        entity_type="settings",
        entity_id="platform",
        metadata={"updated_keys": raw.get("updated_keys", [])},
    )
    return SettingsResponse(
        settings={k: SettingValueResponse(**v) for k, v in raw["settings"].items()},
        updated_keys=raw.get("updated_keys", []),
    )
