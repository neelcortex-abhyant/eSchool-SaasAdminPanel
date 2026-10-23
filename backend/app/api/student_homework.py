"""Student homework listing and submission (Module 3).

Uses legacy personal-access-token student auth (``require_student_user``).
Student identity is resolved from the authenticated principal — never from a
client-supplied student_id. Class-section / session / school scope is enforced
in ``school_homework`` against the Student row for that user.
"""

from __future__ import annotations

from typing import Tuple

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import require_student_user
from app.core.config import get_settings
from app.models.tables import School, User
from app.services.v1 import school_homework as homework_svc
from app.services.v1.school_academics import AcademicError

router = APIRouter(tags=["student-homework"])


class StudentSubmissionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text_response: str | None = Field(default=None, max_length=50000)
    # Metadata only — binary files use …/my-submission/attachments.
    attachments: list[dict] | None = None


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


async def _read_upload(file: UploadFile) -> tuple[bytes, str | None]:
    settings = get_settings()
    limit = max(settings.document_max_image_bytes, settings.document_max_file_bytes)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(status_code=422, detail="File exceeds maximum allowed size")
        chunks.append(chunk)
    return b"".join(chunks), file.filename


@router.get("/student/homework")
def student_list_homework(
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    subject_id: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
):
    db, user, school = tenant
    return _run(
        lambda: homework_svc.list_student_homework(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            subject_id=subject_id,
            status_filter=status_filter,
        )
    )


@router.get("/student/homework/{homework_id}")
def student_get_homework(
    homework_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(
        lambda: homework_svc.get_student_homework(db, school.id, user, homework_id)
    )


@router.post("/student/homework/{homework_id}/submissions", status_code=201)
def student_submit_homework(
    homework_id: int,
    body: StudentSubmissionBody,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(
        lambda: homework_svc.submit_homework(
            db,
            school.id,
            user,
            homework_id,
            body.model_dump(exclude_unset=True),
        )
    )


@router.get("/student/homework/{homework_id}/my-submission")
def student_my_submission(
    homework_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(lambda: homework_svc.get_my_submission(db, school.id, user, homework_id))


@router.post(
    "/student/homework/{homework_id}/my-submission/attachments",
    status_code=201,
)
async def student_upload_submission_attachment(
    homework_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
    file: UploadFile = File(...),
):
    """Binary submission attachment via document_storage; 503 if not configured."""
    db, user, school = tenant
    data, filename = await _read_upload(file)
    return _run(
        lambda: homework_svc.append_stored_attachment_to_submission(
            db,
            school.id,
            user,
            homework_id,
            file_bytes=data,
            claimed_filename=filename or file.filename,
        )
    )


@router.get("/student/assignment-status")
def student_assignment_status(
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: str | None = Query(default=None, alias="status"),
):
    db, user, school = tenant
    return _run(
        lambda: homework_svc.student_assignment_status(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
        )
    )
