"""School Admin self endpoints — scoped by authenticated user.school_id."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, assert_school_scope, require_school_admin
from app.schemas.v1.schools import SchoolResponse
from app.schemas.v1.users import UserResponse
from app.services.v1 import school_service

router = APIRouter(prefix="/school-admin", tags=["v1-school-admin"])


@router.get("/me", response_model=UserResponse)
def school_admin_me(auth: Annotated[AuthContext, Depends(require_school_admin)]) -> UserResponse:
    return UserResponse.model_validate(auth.user)


@router.get("/school", response_model=SchoolResponse)
def school_admin_own_school(
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    """Return the school bound to the authenticated School Admin (server-side school_id)."""
    try:
        school = school_service.get_school(db, auth.user.school_id)  # type: ignore[arg-type]
    except school_service.SchoolServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SchoolResponse.model_validate(school)


@router.get("/schools/{school_id}", response_model=SchoolResponse)
def school_admin_school_by_id(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    """School data only when school_id matches auth.user.school_id (tenant isolation)."""
    assert_school_scope(auth, school_id)
    try:
        school = school_service.get_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SchoolResponse.model_validate(school)
