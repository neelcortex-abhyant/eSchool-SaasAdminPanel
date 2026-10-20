"""School Admin RBAC catalog and the cross-school admin list.

/api/v1/super-admin/roles, /permissions and /school-admins. Per-school admin
CRUD stays in schools.py under /schools/{school_id}/admins.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.schemas.v1.school_admins import (
    PermissionListResponse,
    RoleListResponse,
    SchoolAdminListResponse,
    SchoolAdminResponse,
)
from app.services.v1 import rbac, school_admin_service, school_service

router = APIRouter(tags=["v1-super-admin-school-admins"])


@router.get("/roles", response_model=RoleListResponse)
def list_roles(_auth: Annotated[AuthContext, Depends(require_super_admin)]) -> RoleListResponse:
    """Roles that can be assigned to School Admins, with the permissions each grants."""
    return RoleListResponse(items=rbac.role_catalog())


@router.get("/permissions", response_model=PermissionListResponse)
def list_permissions(_auth: Annotated[AuthContext, Depends(require_super_admin)]) -> PermissionListResponse:
    """Every School Admin permission key."""
    return PermissionListResponse(items=rbac.permission_catalog())


@router.get("/school-admins", response_model=SchoolAdminListResponse)
def list_all_school_admins(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    school_id: int | None = Query(default=None, ge=1, description="Only admins of this school. 404 if the school does not exist."),
    q: str | None = Query(default=None, description="Case-insensitive partial match on first name, last name, full name or email."),
    status_filter: int | None = Query(default=None, alias="status", ge=0, le=1, description="1 = active, 0 = inactive. Omit for both."),
    role: str | None = Query(default=None, description="Admin role key from GET /super-admin/roles."),
    sort: str | None = Query(default=None, description=school_admin_service.ADMIN_SORT_HELP),
) -> SchoolAdminListResponse:
    """School admins across all schools. Same filters as /schools/{school_id}/admins."""
    try:
        rows, total = school_admin_service.list_school_admins(
            db, school_id, page=page, page_size=page_size, q=q, status=status_filter, role=role, sort=sort,
        )
    except (school_service.SchoolServiceError, school_admin_service.SchoolAdminServiceError) as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SchoolAdminListResponse(
        items=[SchoolAdminResponse(**item) for item in school_admin_service.describe_admins(db, rows)],
        total=total,
        page=page,
        page_size=page_size,
    )
