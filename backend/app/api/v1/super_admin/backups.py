"""Super Admin platform backup / restore routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_super_admin
from app.services.v1 import platform_backup_service as backup_svc
from app.services.v1.school_academics import AcademicError

router = APIRouter(prefix="/backups", tags=["v1-super-admin-backups"])


class RestoreBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: str = Field(..., min_length=1, max_length=32)


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_backup(
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: backup_svc.create_backup(db, auth.user))


@router.get("")
def list_backups(
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: backup_svc.list_backups(db, page=page, page_size=page_size))


@router.get("/{backup_id}")
def get_backup(
    backup_id: int,
    _auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: backup_svc.get_backup(db, backup_id))


@router.post("/{backup_id}/restore")
def restore_backup(
    backup_id: int,
    body: RestoreBody,
    auth: Annotated[AuthContext, Depends(require_super_admin)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: backup_svc.request_restore(db, auth.user, backup_id, body.confirmation)
    )
