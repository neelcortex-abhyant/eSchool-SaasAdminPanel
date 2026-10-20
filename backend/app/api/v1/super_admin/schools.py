from __future__ import annotations

import logging
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
    SchoolAdminRolesRequest,
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
from app.models.v1.user import STATUS_ACTIVE
from app.services.v1 import audit_service, password_reset_service, school_admin_service, school_service

router = APIRouter(prefix="/schools", tags=["v1-super-admin-schools"])
logger = logging.getLogger("eschool.school_admins")


def _http(exc: school_service.SchoolServiceError | school_admin_service.SchoolAdminServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _audited(db: Session, detail: str, work, audit):
    """Run work uncommitted, then commit it with the audit row (same as plans.py)."""
    try:
        result = work()
    except (school_service.SchoolServiceError, school_admin_service.SchoolAdminServiceError) as exc:
        db.rollback()
        raise _http(exc) from exc
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail=detail) from None
    try:
        audit(result)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail=detail) from None
    return result


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
    status_filter: int | None = Query(
        default=None,
        alias="status",
        ge=0,
        le=1,
        description="Optional. 1 = active, 0 = inactive. Omit to include both. Any other value is rejected.",
    ),
    code: str | None = Query(default=None),
    name: str | None = Query(default=None, description="Case-insensitive partial match on school name."),
    support_email: str | None = Query(
        default=None,
        description="Case-insensitive partial match on support_email. Combine with other filters.",
    ),
    q: str | None = Query(
        default=None,
        description="Case-insensitive partial match on school name or school code.",
    ),
    include_deleted: bool = Query(default=False),
    sort: str | None = Query(
        default=None,
        description=(
            "name, -name, created_at, or -created_at. "
            "Omitted sort is newest id first. id is the tie-breaker."
        ),
    ),
) -> SchoolListResponse:
    try:
        rows, total = school_service.list_schools(
            db,
            page=page,
            page_size=page_size,
            status=status_filter,
            code=code,
            name=name,
            support_email=support_email,
            q=q,
            sort=sort,
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


def _status_audit_metadata(previous_status: int, previous_installed: int, school) -> dict:
    return {
        "previous_status": previous_status,
        "previous_installed": previous_installed,
        "status": school.status,
        "installed": school.installed,
    }


@router.post("/{school_id}/activate", response_model=SchoolResponse)
def activate_school(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        current = school_service.get_school(db, school_id)
        previous_status = current.status
        previous_installed = current.installed
        school = school_service.activate_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.activate", entity_type="school",
        entity_id=school.id, school_id=school.id,
        metadata=_status_audit_metadata(previous_status, previous_installed, school),
    )
    return SchoolResponse.model_validate(school)


@router.post("/{school_id}/suspend", response_model=SchoolResponse)
def suspend_school(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        current = school_service.get_school(db, school_id)
        previous_status = current.status
        previous_installed = current.installed
        school = school_service.suspend_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.suspend", entity_type="school",
        entity_id=school.id, school_id=school.id,
        metadata=_status_audit_metadata(previous_status, previous_installed, school),
    )
    return SchoolResponse.model_validate(school)


@router.post("/{school_id}/deactivate", response_model=SchoolResponse)
def deactivate_school(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    try:
        current = school_service.get_school(db, school_id)
        previous_status = current.status
        previous_installed = current.installed
        school = school_service.deactivate_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise _http(exc) from exc
    audit_service.record_audit(
        db, actor=auth.user, action="school.deactivate", entity_type="school",
        entity_id=school.id, school_id=school.id,
        metadata=_status_audit_metadata(previous_status, previous_installed, school),
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
    """Create a School Admin. Without a password, an invitation link is emailed instead.

    The account, its roles, any setup token and the audit row commit together.
    Mail is sent only after that commit, and invite_sent reports the real result.
    """
    invite = body.password is None

    def work():
        user = school_admin_service.create_school_admin(
            db,
            school_id,
            email=body.email,
            password=body.password,
            first_name=body.first_name,
            last_name=body.last_name,
            mobile=body.mobile,
            roles=body.roles,
            status=body.status,
            commit=False,
        )
        mail = password_reset_service.prepare_invitation(db, user) if invite else None
        return user, mail

    user, mail = _audited(
        db,
        "School admin could not be created",
        work,
        lambda result: audit_service.record_audit(
            db, actor=auth.user, action="school_admin.create", entity_type="school_admin",
            entity_id=result[0].id, school_id=school_id,
            metadata={
                "email": result[0].email,
                "roles": school_admin_service.describe_admin(db, result[0])["roles"],
                "status": result[0].status,
                "invitation": invite,
            },
        ),
    )
    invite_sent = _deliver_invitation(db, auth, user, school_id, mail) if invite else None
    return _admin_response(db, user, invite_sent=invite_sent)


def _deliver_invitation(db: Session, auth: AuthContext, user, school_id: int, mail) -> bool:
    """Send a committed invitation and audit the outcome. Never raises for mail problems."""
    sent = password_reset_service.send(mail)
    try:
        audit_service.record_audit(
            db, actor=auth.user, action="school_admin.invite", entity_type="school_admin",
            entity_id=user.id, school_id=school_id, metadata={"invite_sent": sent},
        )
    except Exception:
        logger.exception("school_admin_invite_audit_failed")
    return sent


def _admin_response(db: Session, user, *, invite_sent: bool | None = None) -> SchoolAdminResponse:
    return SchoolAdminResponse(**school_admin_service.describe_admin(db, user), invite_sent=invite_sent)


@router.post("/{school_id}/admins/{admin_id}/invite", response_model=SchoolAdminResponse)
def invite_school_admin(
    school_id: int,
    admin_id: uuid.UUID,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAdminResponse:
    """Email a new password-setup link. Earlier unused links stop working.

    invite_sent=false when mail is not configured or delivery failed.
    """
    try:
        user = school_admin_service.get_school_admin(db, school_id, admin_id)
    except (school_service.SchoolServiceError, school_admin_service.SchoolAdminServiceError) as exc:
        raise _http(exc) from exc
    if user.status != STATUS_ACTIVE:
        raise HTTPException(status_code=422, detail="Activate the account before sending an invitation")
    try:
        mail = password_reset_service.prepare_invitation(db, user)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Invitation could not be created") from None
    return _admin_response(db, user, invite_sent=_deliver_invitation(db, auth, user, school_id, mail))


@router.get("/{school_id}/admins", response_model=SchoolAdminListResponse)
def list_school_admins(
    school_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, description="Case-insensitive partial match on first name, last name, full name or email."),
    status_filter: int | None = Query(default=None, alias="status", ge=0, le=1, description="1 = active, 0 = inactive. Omit for both."),
    role: str | None = Query(default=None, description="Admin role key from GET /super-admin/roles."),
    sort: str | None = Query(default=None, description=school_admin_service.ADMIN_SORT_HELP),
) -> SchoolAdminListResponse:
    try:
        rows, total = school_admin_service.list_school_admins(
            db, school_id, page=page, page_size=page_size, q=q, status=status_filter, role=role, sort=sort,
        )
    except (school_service.SchoolServiceError, school_admin_service.SchoolAdminServiceError) as exc:
        raise _http(exc) from exc
    return SchoolAdminListResponse(
        items=[SchoolAdminResponse(**item) for item in school_admin_service.describe_admins(db, rows)],
        total=total,
        page=page,
        page_size=page_size,
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
    return _admin_response(db, user)


@router.patch("/{school_id}/admins/{admin_id}", response_model=SchoolAdminResponse)
def patch_school_admin(
    school_id: int,
    admin_id: uuid.UUID,
    body: SchoolAdminUpdateRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAdminResponse:
    fields_set = body.model_fields_set
    # changed_fields may include "password" as a name; the value is never logged.
    user, _changed = _audited(
        db,
        "School admin could not be updated",
        lambda: school_admin_service.update_school_admin(
            db,
            school_id,
            admin_id,
            first_name=body.first_name,
            last_name=body.last_name,
            mobile=body.mobile,
            mobile_set="mobile" in fields_set,
            password=body.password,
            commit=False,
        ),
        lambda result: audit_service.record_audit(
            db, actor=auth.user, action="school_admin.update", entity_type="school_admin",
            entity_id=result[0].id, school_id=school_id,
            metadata={"email": result[0].email, "changed_fields": result[1]},
        ),
    )
    return _admin_response(db, user)


@router.patch("/{school_id}/admins/{admin_id}/status", response_model=SchoolAdminResponse)
def patch_school_admin_status(
    school_id: int,
    admin_id: uuid.UUID,
    body: SchoolAdminStatusRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAdminResponse:
    user, _previous, _revoked = _audited(
        db,
        "School admin status could not be changed",
        lambda: school_admin_service.set_school_admin_status(
            db, school_id, admin_id, status=body.status, commit=False,
        ),
        lambda result: audit_service.record_audit(
            db, actor=auth.user, action="school_admin.status", entity_type="school_admin",
            entity_id=result[0].id, school_id=school_id,
            metadata={"previous_status": result[1], "status": result[0].status, "sessions_revoked": result[2]},
        ),
    )
    return _admin_response(db, user)


@router.patch("/{school_id}/admins/{admin_id}/roles", response_model=SchoolAdminResponse)
def patch_school_admin_roles(
    school_id: int,
    admin_id: uuid.UUID,
    body: SchoolAdminRolesRequest,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolAdminResponse:
    """Replace the admin's roles (keys from GET /super-admin/roles). Super Admin only."""
    user, _previous, _roles = _audited(
        db,
        "School admin roles could not be changed",
        lambda: school_admin_service.set_school_admin_roles(db, school_id, admin_id, roles=body.roles),
        lambda result: audit_service.record_audit(
            db, actor=auth.user, action="school_admin.roles", entity_type="school_admin",
            entity_id=result[0].id, school_id=school_id,
            metadata={"previous_roles": result[1], "roles": result[2]},
        ),
    )
    return _admin_response(db, user)
