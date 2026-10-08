from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.school_admins import (
    SchoolAdminCreateRequest,
    SchoolAdminListResponse,
    SchoolAdminResponse,
    SchoolAdminStatusRequest,
    SchoolAdminUpdateRequest,
)
from app.schemas.v1.schools import (
    SchoolCreateRequest,
    SchoolListResponse,
    SchoolProvisionResponse,
    SchoolResponse,
    SchoolUpdateRequest,
)
from app.services.v1 import audit_service, school_admin_service, school_service

router = APIRouter(prefix="/schools", tags=["v1-super-admin-schools"])


def _http(exc: school_service.SchoolServiceError | school_admin_service.SchoolAdminServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("", response_model=SchoolResponse, status_code=status.HTTP_201_CREATED)
def create_school(
    body: SchoolCreateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        school = school_service.create_school(
            db,
            name=body.name,
            address=body.address,
            support_phone=body.support_phone,
            support_email=body.support_email,
            tagline=body.tagline,
            logo=body.logo,
            code=body.code,
            domain=body.domain,
        )
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.create", entity_type="school",
        entity_id=school.id, school_id=school.id, metadata={"name": school.name, "code": school.code},
    )
    return SchoolResponse.model_validate(school)


@router.get("", response_model=SchoolListResponse)
def list_schools(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: int | None = Query(default=None, alias="status"),
    code: str | None = Query(default=None),
    name: str | None = Query(default=None),
    include_deleted: bool = Query(default=False),
) -> SchoolListResponse:
    try:
        rows, total = school_service.list_schools(
            db,
            page=page,
            page_size=page_size,
            status=status_filter,
            code=code,
            name=name,
            include_deleted=include_deleted,
        )
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    return SchoolListResponse(
        items=[SchoolResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{school_id}", response_model=SchoolResponse)
def get_school(
    school_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        school = school_service.get_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    return SchoolResponse.model_validate(school)


@router.patch("/{school_id}", response_model=SchoolResponse)
def patch_school(
    school_id: int,
    body: SchoolUpdateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        school = school_service.update_school(
            db,
            school_id,
            name=body.name,
            address=body.address,
            support_phone=body.support_phone,
            support_email=body.support_email,
            tagline=body.tagline,
            logo=body.logo,
            code=body.code,
            domain=body.domain,
        )
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.update", entity_type="school",
        entity_id=school.id, school_id=school.id, metadata={"name": school.name},
    )
    return SchoolResponse.model_validate(school)


@router.delete("/{school_id}", response_model=SchoolResponse)
def delete_school(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        school = school_service.soft_delete_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.delete", entity_type="school",
        entity_id=school.id, school_id=school.id,
    )
    return SchoolResponse.model_validate(school)


@router.post("/{school_id}/activate", response_model=SchoolResponse)
def activate_school(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        school = school_service.activate_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.activate", entity_type="school",
        entity_id=school.id, school_id=school.id, metadata={"status": school.status},
    )
    return SchoolResponse.model_validate(school)


@router.post("/{school_id}/suspend", response_model=SchoolResponse)
def suspend_school(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        school = school_service.suspend_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.suspend", entity_type="school",
        entity_id=school.id, school_id=school.id, metadata={"status": school.status},
    )
    return SchoolResponse.model_validate(school)


@router.post("/{school_id}/deactivate", response_model=SchoolResponse)
def deactivate_school(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        school = school_service.deactivate_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.deactivate", entity_type="school",
        entity_id=school.id, school_id=school.id, metadata={"status": school.status},
    )
    return SchoolResponse.model_validate(school)


@router.post("/{school_id}/provision", response_model=SchoolProvisionResponse)
def provision_school(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolProvisionResponse:
    """Idempotent shared-Neon school init (session year + active/installed). No physical DB."""
    try:
        school, first = school_service.provision_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.provision", entity_type="school",
        entity_id=school.id, school_id=school.id, metadata={"first_provision": first},
    )
    return SchoolProvisionResponse(
        school=SchoolResponse.model_validate(school),
        provisioned=True,
        first_provision=first,
    )


@router.post(
    "/{school_id}/admins",
    response_model=SchoolAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_school_admin(
    school_id: int,
    body: SchoolAdminCreateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAdminResponse:
    try:
        user = school_admin_service.create_school_admin(
            db,
            school_id,
            email=body.email,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
            mobile=body.mobile,
        )
    except (school_service.SchoolServiceError, school_admin_service.SchoolAdminServiceError) as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school_admin.create", entity_type="school_admin",
        entity_id=user.id, school_id=school_id, metadata={"email": user.email},
    )
    return SchoolAdminResponse.model_validate(user)


@router.get("/{school_id}/admins", response_model=SchoolAdminListResponse)
def list_school_admins(
    school_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAdminListResponse:
    try:
        items = school_admin_service.list_school_admins(db, school_id)
    except (school_service.SchoolServiceError, school_admin_service.SchoolAdminServiceError) as exc:
        raise _http(exc) from exc
    return SchoolAdminListResponse(
        items=[SchoolAdminResponse.model_validate(u) for u in items],
    )


@router.get("/{school_id}/admins/{admin_id}", response_model=SchoolAdminResponse)
def get_school_admin(
    school_id: int,
    admin_id: uuid.UUID,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAdminResponse:
    try:
        user = school_admin_service.get_school_admin(db, school_id, admin_id)
    except (school_service.SchoolServiceError, school_admin_service.SchoolAdminServiceError) as exc:
        raise _http(exc) from exc
    return SchoolAdminResponse.model_validate(user)


@router.patch("/{school_id}/admins/{admin_id}", response_model=SchoolAdminResponse)
def patch_school_admin(
    school_id: int,
    admin_id: uuid.UUID,
    body: SchoolAdminUpdateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAdminResponse:
    fields_set = body.model_fields_set
    try:
        user = school_admin_service.update_school_admin(
            db,
            school_id,
            admin_id,
            first_name=body.first_name,
            last_name=body.last_name,
            mobile=body.mobile,
            mobile_set="mobile" in fields_set,
            password=body.password,
        )
    except (school_service.SchoolServiceError, school_admin_service.SchoolAdminServiceError) as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school_admin.update", entity_type="school_admin",
        entity_id=user.id, school_id=school_id, metadata={"email": user.email},
    )
    return SchoolAdminResponse.model_validate(user)


@router.patch("/{school_id}/admins/{admin_id}/status", response_model=SchoolAdminResponse)
def patch_school_admin_status(
    school_id: int,
    admin_id: uuid.UUID,
    body: SchoolAdminStatusRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAdminResponse:
    try:
        user = school_admin_service.set_school_admin_status(
            db,
            school_id,
            admin_id,
            status=body.status,
        )
    except (school_service.SchoolServiceError, school_admin_service.SchoolAdminServiceError) as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school_admin.status", entity_type="school_admin",
        entity_id=user.id, school_id=school_id, metadata={"status": user.status},
    )
    return SchoolAdminResponse.model_validate(user)
