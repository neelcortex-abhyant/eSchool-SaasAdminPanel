"""School add-on assignments — /api/v1/super-admin/schools/{school_id}/addons."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.addons import (
    SchoolAddonAssignRequest,
    SchoolAddonListResponse,
    SchoolAddonResponse,
    SchoolAddonStatusRequest,
)
from app.services.v1 import addon_service, audit_service

router = APIRouter(prefix="/schools/{school_id}/addons", tags=["v1-super-admin-school-addons"])


def _http(exc: addon_service.AddonServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("", response_model=SchoolAddonResponse, status_code=status.HTTP_201_CREATED)
def assign_addon(
    school_id: int,
    body: SchoolAddonAssignRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAddonResponse:
    try:
        row = addon_service.assign_addon(
            db,
            school_id,
            addon_id=body.addon_id,
            subscription_id=body.subscription_id,
            start_date=body.start_date,
            end_date=body.end_date,
        )
    except addon_service.AddonServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="addon.assign", entity_type="addon_subscription",
        entity_id=row.id, school_id=school_id, metadata={"addon_id": row.addon_id, "subscription_id": row.subscription_id},
    )
    return SchoolAddonResponse.model_validate(row)


@router.get("", response_model=SchoolAddonListResponse)
def list_school_addons(
    school_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: int | None = Query(default=None, alias="status"),
) -> SchoolAddonListResponse:
    try:
        rows, total = addon_service.list_school_addons(
            db, school_id, page=page, page_size=page_size, status=status_filter
        )
    except addon_service.AddonServiceError as exc:
        raise _http(exc) from exc
    return SchoolAddonListResponse(
        items=[SchoolAddonResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{assignment_id}", response_model=SchoolAddonResponse)
def get_school_addon(
    school_id: int,
    assignment_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAddonResponse:
    try:
        row = addon_service.get_school_addon(db, school_id, assignment_id)
    except addon_service.AddonServiceError as exc:
        raise _http(exc) from exc
    return SchoolAddonResponse.model_validate(row)


@router.patch("/{assignment_id}/status", response_model=SchoolAddonResponse)
def patch_school_addon_status(
    school_id: int,
    assignment_id: int,
    body: SchoolAddonStatusRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAddonResponse:
    try:
        row = addon_service.set_school_addon_status(
            db, school_id, assignment_id, status=body.status
        )
    except addon_service.AddonServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="addon.assignment_status", entity_type="addon_subscription",
        entity_id=row.id, school_id=school_id, metadata={"status": row.status, "addon_id": row.addon_id},
    )
    return SchoolAddonResponse.model_validate(row)
