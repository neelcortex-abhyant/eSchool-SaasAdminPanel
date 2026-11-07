"""School Admin branch management — same school_id, never a second school."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_school_permission
from app.schemas.v1 import school_branches as schemas
from app.schemas.v1.school_admin_erp_responses import json_response
from app.services.v1 import rbac
from app.services.v1 import school_branches as branches_svc

router = APIRouter(tags=["v1-school-admin-branches"])

require_school = require_school_permission(rbac.PERM_SCHOOL)
require_dashboard = require_school_permission(rbac.PERM_DASHBOARD)


def _school_id(auth: AuthContext) -> int:
    if auth.user.school_id is None:
        raise HTTPException(status_code=403, detail="No school assigned")
    return int(auth.user.school_id)


def _run(fn):
    try:
        return fn()
    except branches_svc.BranchError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    "/branches",
    responses=json_response(schemas.BranchListOut),
)
def list_branches(
    auth: Annotated[AuthContext, Depends(require_dashboard)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    school_id = _school_id(auth)
    allowed, is_full = branches_svc.allowed_branch_ids_for_user(db, auth.user)
    items = branches_svc.list_branches(db, school_id, include_disabled=is_full)
    if not is_full:
        allowed_set = set(allowed)
        items = [i for i in items if i["id"] in allowed_set]
    return {"items": items}


@router.post(
    "/branches",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(schemas.BranchOut, status_code=201),
)
def create_branch(
    body: schemas.BranchCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Full school_admin only (school.manage). Creates Branch N under same school."""
    roles = rbac.effective_roles(db, auth.user)
    if rbac.ADMIN_ROLE_SCHOOL not in roles:
        raise HTTPException(status_code=403, detail="Only school admins can create branches")
    return _run(
        lambda: branches_svc.create_branch(
            db,
            _school_id(auth),
            name=body.name,
            code=body.code,
            address=body.address or "",
        )
    )


@router.get(
    "/branches/{branch_id}",
    responses=json_response(schemas.BranchOut),
)
def get_branch(
    branch_id: int,
    auth: Annotated[AuthContext, Depends(require_dashboard)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    school_id = _school_id(auth)
    allowed, is_full = branches_svc.allowed_branch_ids_for_user(db, auth.user)
    if not is_full and branch_id not in allowed:
        raise HTTPException(status_code=403, detail="Not authorized for this branch")
    return _run(lambda: branches_svc.get_branch(db, school_id, branch_id))


@router.patch(
    "/branches/{branch_id}",
    responses=json_response(schemas.BranchOut),
)
def update_branch(
    branch_id: int,
    body: schemas.BranchUpdateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    roles = rbac.effective_roles(db, auth.user)
    if rbac.ADMIN_ROLE_SCHOOL not in roles:
        raise HTTPException(status_code=403, detail="Only school admins can update branches")
    data = body.model_dump(exclude_unset=True)
    return _run(lambda: branches_svc.update_branch(db, _school_id(auth), branch_id, data))


@router.delete(
    "/branches/{branch_id}",
    responses=json_response(schemas.BranchDeletedOut),
)
def delete_branch(
    branch_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    roles = rbac.effective_roles(db, auth.user)
    if rbac.ADMIN_ROLE_SCHOOL not in roles:
        raise HTTPException(status_code=403, detail="Only school admins can delete branches")
    return _run(lambda: branches_svc.soft_delete_branch(db, _school_id(auth), branch_id))


@router.put(
    "/branches/{branch_id}/admins",
    responses=json_response(schemas.BranchAdminsOut),
)
def put_branch_admins(
    branch_id: int,
    body: schemas.BranchAdminsBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    roles = rbac.effective_roles(db, auth.user)
    if rbac.ADMIN_ROLE_SCHOOL not in roles:
        raise HTTPException(status_code=403, detail="Only school admins can assign branch admins")
    return _run(
        lambda: branches_svc.set_branch_admins(
            db, _school_id(auth), branch_id, list(body.user_ids)
        )
    )


@router.get("/branches/{branch_id}/admins")
def get_branch_admins(
    branch_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: {"items": branches_svc.list_branch_admins(db, _school_id(auth), branch_id)}
    )


@router.get("/me/branches")
def me_branches(
    auth: Annotated[AuthContext, Depends(require_dashboard)],
    db: Annotated[Session, Depends(central_db)],
    x_branch_id: Annotated[int | None, Header(alias="X-Branch-Id")] = None,
) -> dict:
    return branches_svc.me_branches_payload(db, auth.user, active_branch_id=x_branch_id)
