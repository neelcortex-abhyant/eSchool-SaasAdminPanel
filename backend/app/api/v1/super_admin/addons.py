"""Super Admin add-on catalog — /api/v1/super-admin/addons."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.addons import (
    AddonCreateRequest,
    AddonListResponse,
    AddonResponse,
    AddonStatusRequest,
    AddonUpdateRequest,
)
from app.services.v1 import addon_service, audit_service

router = APIRouter(prefix="/addons", tags=["v1-super-admin-addons"])


def _http(exc: addon_service.AddonServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("", response_model=AddonResponse, status_code=status.HTTP_201_CREATED)
def create_addon(
    body: AddonCreateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> AddonResponse:
    try:
        addon = addon_service.create_addon(
            db, name=body.name, description=body.description, price=body.price
        )
    except addon_service.AddonServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db,
        actor=auth.user,
        action="addon.create",
        entity_type="addon",
        entity_id=addon.id,
        metadata={"name": addon.name},
    )
    return AddonResponse.model_validate(addon)


@router.get("", response_model=AddonListResponse)
def list_addons(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: int | None = Query(default=None, alias="status"),
    name: str | None = Query(default=None),
) -> AddonListResponse:
    try:
        rows, total = addon_service.list_addons(
            db, page=page, page_size=page_size, status=status_filter, name=name
        )
    except addon_service.AddonServiceError as exc:
        raise _http(exc) from exc
    return AddonListResponse(
        items=[AddonResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{addon_id}", response_model=AddonResponse)
def get_addon(
    addon_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> AddonResponse:
    try:
        addon = addon_service.get_addon(db, addon_id)
    except addon_service.AddonServiceError as exc:
        raise _http(exc) from exc
    return AddonResponse.model_validate(addon)


@router.patch("/{addon_id}", response_model=AddonResponse)
def patch_addon(
    addon_id: int,
    body: AddonUpdateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> AddonResponse:
    try:
        addon = addon_service.update_addon(
            db,
            addon_id,
            name=body.name,
            description=body.description,
            price=body.price,
        )
    except addon_service.AddonServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db,
        actor=auth.user,
        action="addon.update",
        entity_type="addon",
        entity_id=addon.id,
        metadata={"name": addon.name},
    )
    return AddonResponse.model_validate(addon)


@router.patch("/{addon_id}/status", response_model=AddonResponse)
def patch_addon_status(
    addon_id: int,
    body: AddonStatusRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> AddonResponse:
    try:
        addon = addon_service.set_addon_status(db, addon_id, status=body.status)
    except addon_service.AddonServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db,
        actor=auth.user,
        action="addon.status",
        entity_type="addon",
        entity_id=addon.id,
        metadata={"status": addon.status},
    )
    return AddonResponse.model_validate(addon)
