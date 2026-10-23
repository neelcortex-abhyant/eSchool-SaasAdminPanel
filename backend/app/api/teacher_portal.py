"""Teacher teaching APIs (Modules 1–6) using ``require_teacher_user`` PAT auth.

Paths under ``/api/teacher/*`` that do not collide with legacy stubs.
``teacher_user_id`` is always taken from the authenticated principal.

Frontend auth / error-envelope notes: ``docs/TEACHER_PORTAL_AUTH.md``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Tuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.deps import require_teacher_user
from app.core.config import get_settings
from app.models.tables import School, User
from app.services.v1 import teacher_portal as portal
from app.services.v1.school_academics import AcademicError

router = APIRouter(tags=["teacher-portal"])


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


# --- Bodies (forbid client teacher/school/evaluator smuggling) ---


class HomeworkCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=20000)
    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    assigned_date: date
    deadline_at: datetime
    max_marks: float | None = Field(default=None, ge=0)
    allow_late: bool = True
    attachments: list[dict] = Field(default_factory=list)


class HomeworkUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=20000)
    session_year_id: int | None = Field(default=None, ge=1)
    class_section_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    assigned_date: date | None = None
    deadline_at: datetime | None = None
    max_marks: float | None = Field(default=None, ge=0)
    allow_late: bool | None = None
    attachments: list[dict] | None = None


class EvaluationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    marks: float | None = Field(default=None, ge=0)
    grade: str | None = Field(default=None, max_length=64)
    feedback: str | None = Field(default=None, max_length=20000)


class MaterialCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    resource_type: str = Field(min_length=1, max_length=32)
    chapter: str | None = Field(default=None, max_length=255)
    topic: str | None = Field(default=None, max_length=255)
    external_url: str | None = Field(default=None, max_length=2048)


class MaterialUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    session_year_id: int | None = Field(default=None, ge=1)
    class_section_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    chapter: str | None = Field(default=None, max_length=255)
    topic: str | None = Field(default=None, max_length=255)
    external_url: str | None = Field(default=None, max_length=2048)


class MarkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: int = Field(ge=1)
    marks_obtained: float | None = Field(default=None, ge=0)
    status: str = Field(default="present", max_length=32)
    reason: str | None = Field(default=None, max_length=512)


class MarkBulkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MarkBody] = Field(min_length=1, max_length=200)


class AssessmentCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=20000)
    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    duration_minutes: int = Field(ge=1, le=600)
    total_marks: float = Field(gt=0)
    passing_marks: float = Field(ge=0)
    available_from: datetime
    available_until: datetime


# --- Identity / assignments / timetable ---


@router.get("/teacher/me")
def teacher_me(tenant: Tuple[Session, User, School] = Depends(require_teacher_user)):
    db, user, school = tenant
    return _run(lambda: portal.me(db, school.id, user))


@router.get("/teacher/assignments")
def teacher_assignments(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    subject_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    session_year_id: int | None = Query(default=None, ge=1),
):
    db, user, school = tenant
    return _run(
        lambda: portal.my_assignments(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            subject_id=subject_id,
            class_section_id=class_section_id,
            session_year_id=session_year_id,
        )
    )


@router.get("/teacher/timetable/daily")
def teacher_timetable_daily(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    day: str = Query(...),
    session_year_id: int = Query(..., ge=1),
):
    db, user, school = tenant
    return _run(
        lambda: portal.my_timetable_daily(
            db, school.id, user, day=day, session_year_id=session_year_id
        )
    )


@router.get("/teacher/timetable/weekly")
def teacher_timetable_weekly(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    session_year_id: int = Query(..., ge=1),
):
    db, user, school = tenant
    return _run(
        lambda: portal.my_timetable_weekly(db, school.id, user, session_year_id=session_year_id)
    )


@router.get("/teacher/timetable")
def teacher_timetable_entries(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    session_year_id: int = Query(..., ge=1),
    day: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    db, user, school = tenant
    return _run(
        lambda: portal.my_timetable_entries(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            session_year_id=session_year_id,
            day=day,
        )
    )


# --- Homework ---


@router.post("/teacher/homework", status_code=201)
def teacher_create_homework(
    body: HomeworkCreateBody,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(
        lambda: portal.create_homework(db, school.id, user, body.model_dump(exclude_unset=True))
    )


@router.get("/teacher/homework")
def teacher_list_homework(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session_year_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    q: str = Query(default=""),
):
    db, user, school = tenant
    return _run(
        lambda: portal.list_homework(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            session_year_id=session_year_id,
            class_section_id=class_section_id,
            subject_id=subject_id,
            q=q,
        )
    )


@router.get("/teacher/homework/{homework_id}")
def teacher_get_homework(
    homework_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(lambda: portal.get_homework(db, school.id, user, homework_id))


@router.patch("/teacher/homework/{homework_id}")
def teacher_update_homework(
    homework_id: int,
    body: HomeworkUpdateBody,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(
        lambda: portal.update_homework(
            db, school.id, user, homework_id, body.model_dump(exclude_unset=True)
        )
    )


@router.delete("/teacher/homework/{homework_id}")
def teacher_delete_homework(
    homework_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(lambda: portal.delete_homework(db, school.id, user, homework_id))


@router.get("/teacher/homework/{homework_id}/submissions")
def teacher_list_submissions(
    homework_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: str | None = Query(default=None, alias="status"),
    is_late: bool | None = Query(default=None),
):
    db, user, school = tenant
    return _run(
        lambda: portal.list_submissions(
            db,
            school.id,
            user,
            homework_id,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            is_late=is_late,
        )
    )


@router.get("/teacher/homework/{homework_id}/summary")
def teacher_homework_summary(
    homework_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(lambda: portal.homework_summary(db, school.id, user, homework_id))


@router.post("/teacher/homework/{homework_id}/attachments", status_code=201)
async def teacher_homework_attachment(
    homework_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    file: UploadFile = File(...),
):
    db, user, school = tenant
    data, filename = await _read_upload(file)
    return _run(
        lambda: portal.append_homework_attachment(
            db,
            school.id,
            user,
            homework_id,
            file_bytes=data,
            claimed_filename=filename or file.filename,
        )
    )


@router.patch("/teacher/homework-submissions/{submission_id}/evaluation")
def teacher_evaluate_submission(
    submission_id: int,
    body: EvaluationBody,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(
        lambda: portal.evaluate_submission(
            db, school.id, user, submission_id, body.model_dump(exclude_unset=True)
        )
    )


# --- Study materials ---


@router.post("/teacher/study-materials", status_code=201)
def teacher_create_material(
    body: MaterialCreateBody,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    payload = body.model_dump(exclude_unset=True)
    if str(payload.get("resource_type") or "").lower() == "file":
        raise HTTPException(
            status_code=422,
            detail="resource_type=file requires multipart upload at POST /teacher/study-materials/upload",
        )
    return _run(lambda: portal.create_material(db, school.id, user, payload))


@router.post("/teacher/study-materials/upload", status_code=201)
async def teacher_upload_material(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    file: UploadFile = File(...),
    title: str = Form(...),
    session_year_id: int = Form(...),
    class_section_id: int = Form(...),
    subject_id: int = Form(...),
    description: str | None = Form(default=None),
    chapter: str | None = Form(default=None),
    topic: str | None = Form(default=None),
):
    db, user, school = tenant
    data, filename = await _read_upload(file)
    body = {
        "title": title,
        "description": description,
        "session_year_id": session_year_id,
        "class_section_id": class_section_id,
        "subject_id": subject_id,
        "resource_type": "file",
        "chapter": chapter,
        "topic": topic,
    }
    return _run(
        lambda: portal.create_material(
            db,
            school.id,
            user,
            body,
            file_bytes=data,
            claimed_filename=filename or file.filename,
        )
    )


@router.get("/teacher/study-materials")
def teacher_list_materials(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session_year_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    resource_type: str | None = Query(default=None),
    q: str = Query(default=""),
):
    db, user, school = tenant
    return _run(
        lambda: portal.list_materials(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            session_year_id=session_year_id,
            class_section_id=class_section_id,
            subject_id=subject_id,
            resource_type=resource_type,
            q=q,
        )
    )


@router.get("/teacher/study-materials/{material_id}")
def teacher_get_material(
    material_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(lambda: portal.get_material(db, school.id, user, material_id))


@router.patch("/teacher/study-materials/{material_id}")
def teacher_update_material(
    material_id: int,
    body: MaterialUpdateBody,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(
        lambda: portal.update_material(
            db, school.id, user, material_id, body.model_dump(exclude_unset=True)
        )
    )


@router.delete("/teacher/study-materials/{material_id}")
def teacher_delete_material(
    material_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(lambda: portal.delete_material(db, school.id, user, material_id))


@router.get("/teacher/study-materials/{material_id}/download")
def teacher_download_material(
    material_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant

    def _download():
        data, content_type, download_name = portal.download_material(
            db, school.id, user, material_id
        )
        headers: dict[str, Any] = {}
        if download_name:
            headers["Content-Disposition"] = f'attachment; filename="{download_name}"'
        return Response(content=data, media_type=content_type, headers=headers)

    return _run(_download)


# --- Offline exam marks ---


@router.get("/teacher/offline-exam-schedules")
def teacher_list_schedules(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    exam_id: int | None = Query(default=None, ge=1),
    session_year_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    exam_date: date | None = Query(default=None),
):
    db, user, school = tenant
    return _run(
        lambda: portal.list_my_schedules(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            exam_id=exam_id,
            session_year_id=session_year_id,
            class_section_id=class_section_id,
            subject_id=subject_id,
            exam_date=exam_date,
        )
    )


@router.post("/teacher/offline-exam-schedules/{schedule_id}/marks", status_code=201)
def teacher_upsert_mark(
    schedule_id: int,
    body: MarkBody,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    payload = body.model_dump(exclude_unset=True)
    reason = payload.pop("reason", None)
    return _run(
        lambda: portal.upsert_mark(db, school.id, user, schedule_id, payload, reason=reason)
    )


@router.post("/teacher/offline-exam-schedules/{schedule_id}/marks/bulk")
def teacher_bulk_marks(
    schedule_id: int,
    body: MarkBulkBody,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    items = []
    for item in body.items:
        row = item.model_dump(exclude_unset=True)
        row.pop("reason", None)
        items.append(row)
    return _run(lambda: portal.bulk_upsert_marks(db, school.id, user, schedule_id, items))


@router.get("/teacher/offline-exam-marks")
def teacher_list_marks(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    schedule_id: int = Query(..., ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    student_id: int | None = Query(default=None, ge=1),
):
    db, user, school = tenant
    return _run(
        lambda: portal.list_marks(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            schedule_id=schedule_id,
            student_id=student_id,
        )
    )


@router.get("/teacher/offline-exam-marks/{mark_id}/audits")
def teacher_mark_audits(
    mark_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(lambda: portal.list_mark_audits(db, school.id, user, mark_id))


# --- Online assessments (owned) ---


@router.post("/teacher/online-assessments", status_code=201)
def teacher_create_assessment(
    body: AssessmentCreateBody,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(
        lambda: portal.create_assessment(
            db, school.id, user, body.model_dump(exclude_unset=True)
        )
    )


@router.get("/teacher/online-assessments")
def teacher_list_assessments(
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session_year_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    q: str = Query(default=""),
):
    db, user, school = tenant
    return _run(
        lambda: portal.list_assessments(
            db,
            school.id,
            user,
            page=page,
            page_size=page_size,
            session_year_id=session_year_id,
            class_section_id=class_section_id,
            subject_id=subject_id,
            status=status,
            q=q,
        )
    )


@router.get("/teacher/online-assessments/{assessment_id}")
def teacher_get_assessment(
    assessment_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
):
    db, user, school = tenant
    return _run(lambda: portal.get_assessment(db, school.id, user, assessment_id))


@router.get("/teacher/online-assessments/{assessment_id}/attempts")
def teacher_list_attempts(
    assessment_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_teacher_user),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    db, user, school = tenant
    return _run(
        lambda: portal.list_attempts(
            db, school.id, user, assessment_id, page=page, page_size=page_size
        )
    )
