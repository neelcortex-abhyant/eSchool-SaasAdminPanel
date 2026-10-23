"""Student study-material listing and secure download (Module 4).

Identity from ``require_student_user``; enrollment/class-section scoping in service.
"""

from __future__ import annotations

from typing import Tuple
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_student_user
from app.models.tables import School, User
from app.services.v1 import school_study_materials as materials_svc
from app.services.v1.school_academics import AcademicError

router = APIRouter(tags=["student-study-materials"])


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def _download_response(data: bytes, content_type: str, filename: str | None) -> Response:
    safe_name = (filename or "download").replace('"', "")
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}"; filename*=UTF-8\'\'{quote(safe_name)}',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
    return Response(content=data, media_type=content_type, headers=headers)


@router.get("/student/study-materials")
def student_list_study_materials(
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    subject_id: int | None = Query(default=None, ge=1),
    resource_type: str | None = Query(default=None),
    chapter: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    q: str = Query(default=""),
):
    db, user, school = tenant
    return _run(
        lambda: materials_svc.list_student_materials(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            subject_id=subject_id,
            resource_type=resource_type,
            chapter=chapter,
            topic=topic,
            q=q,
        )
    )


@router.get("/student/study-materials/{material_id}")
def student_get_study_material(
    material_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(
        lambda: materials_svc.get_student_material(db, school.id, user, material_id)
    )


@router.get("/student/study-materials/{material_id}/download")
def student_download_study_material(
    material_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    data, content_type, filename = _run(
        lambda: materials_svc.get_student_file_bytes(db, school.id, user, material_id)
    )
    return _download_response(data, content_type, filename)
