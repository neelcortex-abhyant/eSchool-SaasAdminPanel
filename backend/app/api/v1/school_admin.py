"""School Admin self endpoints — scoped by authenticated user.school_id."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, assert_school_scope, require_school_permission
from app.core.config import get_settings
from app.models.tables import SessionYear
from app.schemas.v1.schools import SchoolResponse
from app.schemas.v1.users import UserResponse
from app.api.v1 import school_admin_academics as academics_routes
from app.services.v1 import person_documents as docs_svc
from app.services.v1 import rbac, school_service
from app.services.v1 import school_academics as academics
from app.services.v1 import school_staff as staff_svc
from app.services.v1 import school_teachers as teachers_svc
from app.services.v1 import school_people as people_svc
from app.services.v1 import school_homework as homework_svc
from app.services.v1 import school_offline_exams as offline_svc
from app.services.v1 import school_online_assessments as oa_svc
from app.services.v1 import school_study_materials as materials_svc
from app.services.v1 import school_timetable as timetable_svc

router = APIRouter(prefix="/school-admin", tags=["v1-school-admin"])

# Basic school context. Every admin role grants dashboard.view.
require_school_context = require_school_permission(rbac.PERM_DASHBOARD)
require_structure_write = require_school_permission(rbac.PERM_SCHOOL)
# Teacher assignments use teachers.manage (same as academics/teacher-assignments).
require_teachers = require_school_permission(rbac.PERM_TEACHERS)
require_staff = require_school_permission(rbac.PERM_STAFF)
require_students = require_school_permission(rbac.PERM_STUDENTS)
require_exams = require_school_permission(rbac.PERM_EXAMS)


def require_teachers_or_staff(
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
) -> AuthContext:
    """Unified people listing: teachers.manage or staff.manage."""
    granted = set(rbac.permissions_for(db, auth.user))
    if rbac.PERM_TEACHERS not in granted and rbac.PERM_STAFF not in granted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    return auth


# Academic structure lives in school_admin_academics.py; inherits this router's tag.
# Mounted first so /academics/... stays distinct from direct /classes and /sessions.
router.include_router(academics_routes.router)


class ClassWriteBody(BaseModel):
    """Create/update body for direct class routes. school_id is never accepted."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=512)
    medium_id: int | None = Field(default=None, ge=1)
    include_semesters: int | None = Field(default=None, ge=0, le=1)


class SectionWriteBody(BaseModel):
    """Create/update body for direct section routes. school_id is never accepted."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=512)
    class_id: int | None = Field(default=None, ge=1)


class SubjectWriteBody(BaseModel):
    """Create/update body for direct subject routes. school_id is never accepted."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=512)
    code: str | None = Field(default=None, max_length=64)
    type: str | None = Field(default=None, max_length=64)
    medium_id: int | None = Field(default=None, ge=1)


class SubjectClassesBody(BaseModel):
    """Replace active class associations for a subject."""

    model_config = ConfigDict(extra="forbid")

    class_ids: list[int] = Field(default_factory=list)


class TeacherAssignmentWriteBody(BaseModel):
    """Create/update teacher–subject assignment. school_id is never accepted."""

    model_config = ConfigDict(extra="forbid")

    teacher_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    class_id: int | None = Field(default=None, ge=1)
    section_id: int | None = Field(default=None, ge=1)
    session_id: int | None = Field(default=None, ge=1)
    # Compat aliases used by academics clients.
    class_section_id: int | None = Field(default=None, ge=1)
    session_year_id: int | None = Field(default=None, ge=1)


class TeacherCreateBody(BaseModel):
    """Create a Teacher account + Staff row. school_id / roles forbidden."""

    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    email: EmailStr = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    mobile: str | None = Field(default=None, max_length=255)
    gender: str | None = Field(default=None, max_length=16)
    dob: date | None = None
    current_address: str | None = Field(default=None, max_length=512)
    permanent_address: str | None = Field(default=None, max_length=512)
    country_code: str | None = Field(default=None, max_length=32)
    image: str | None = Field(default=None, max_length=512)
    qualification: str | None = Field(default=None, max_length=512)
    salary: float | None = Field(default=None, ge=0)
    employee_id: str | None = Field(default=None, max_length=64)
    employee_code: str | None = Field(default=None, max_length=64)
    joining_date: date | None = None
    employment_status: str | None = Field(default=None, max_length=32)
    employment_type: str | None = Field(default=None, max_length=32)
    department: str | None = Field(default=None, max_length=128)
    designation: str | None = Field(default=None, max_length=128)


class TeacherUpdateBody(BaseModel):
    """Partial teacher profile / employment update. Account status uses …/status."""

    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=255)
    gender: str | None = Field(default=None, max_length=16)
    dob: date | None = None
    current_address: str | None = Field(default=None, max_length=512)
    permanent_address: str | None = Field(default=None, max_length=512)
    country_code: str | None = Field(default=None, max_length=32)
    image: str | None = Field(default=None, max_length=512)
    qualification: str | None = Field(default=None, max_length=512)
    salary: float | None = Field(default=None, ge=0)
    employee_id: str | None = Field(default=None, max_length=64)
    employee_code: str | None = Field(default=None, max_length=64)
    joining_date: date | None = None
    employment_status: str | None = Field(default=None, max_length=32)
    employment_type: str | None = Field(default=None, max_length=32)
    department: str | None = Field(default=None, max_length=128)
    designation: str | None = Field(default=None, max_length=128)


class TeacherStatusBody(BaseModel):
    """Account activation. Maps to User.status (0=inactive, 1=active)."""

    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=1)


class StaffCreateBody(BaseModel):
    """Create non-teaching Staff account + Staff row. Never assigns Teacher."""

    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    email: EmailStr = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    mobile: str | None = Field(default=None, max_length=255)
    gender: str | None = Field(default=None, max_length=16)
    dob: date | None = None
    current_address: str | None = Field(default=None, max_length=512)
    permanent_address: str | None = Field(default=None, max_length=512)
    country_code: str | None = Field(default=None, max_length=32)
    image: str | None = Field(default=None, max_length=512)
    qualification: str | None = Field(default=None, max_length=512)
    salary: float | None = Field(default=None, ge=0)
    employee_id: str | None = Field(default=None, max_length=64)
    employee_code: str | None = Field(default=None, max_length=64)
    joining_date: date | None = None
    employment_status: str | None = Field(default=None, max_length=32)
    employment_type: str | None = Field(default=None, max_length=32)
    department: str | None = Field(default=None, max_length=128)
    designation: str | None = Field(default=None, max_length=128)


class StaffUpdateBody(BaseModel):
    """Partial non-teaching staff update. Account status uses …/status."""

    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=128)
    last_name: str | None = Field(default=None, min_length=1, max_length=128)
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=255)
    gender: str | None = Field(default=None, max_length=16)
    dob: date | None = None
    current_address: str | None = Field(default=None, max_length=512)
    permanent_address: str | None = Field(default=None, max_length=512)
    country_code: str | None = Field(default=None, max_length=32)
    image: str | None = Field(default=None, max_length=512)
    qualification: str | None = Field(default=None, max_length=512)
    salary: float | None = Field(default=None, ge=0)
    employee_id: str | None = Field(default=None, max_length=64)
    employee_code: str | None = Field(default=None, max_length=64)
    joining_date: date | None = None
    employment_status: str | None = Field(default=None, max_length=32)
    employment_type: str | None = Field(default=None, max_length=32)
    department: str | None = Field(default=None, max_length=128)
    designation: str | None = Field(default=None, max_length=128)


class StaffStatusBody(BaseModel):
    """Account activation. Maps to User.status (0=inactive, 1=active)."""

    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=1)


class GuardianInlineBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_id: int | None = Field(default=None, ge=1)
    relationship: str = Field(min_length=1, max_length=32)
    first_name: str | None = Field(default=None, max_length=128)
    last_name: str | None = Field(default=None, max_length=128)
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=32)


class StudentCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    dob: date
    gender: str = Field(min_length=1, max_length=16)
    admission_no: str | None = Field(default=None, max_length=32)
    admission_date: date
    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    roll_number: int | None = Field(default=None, ge=1, le=9999)
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=32)
    current_address: str = Field(min_length=1, max_length=512)
    permanent_address: str | None = Field(default=None, max_length=512)
    status: int | None = Field(default=1, ge=0, le=1)
    guardian: GuardianInlineBody


class StudentUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    dob: date
    gender: str = Field(min_length=1, max_length=16)
    admission_no: str = Field(min_length=1, max_length=32)
    admission_date: date
    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    roll_number: int | None = Field(default=None, ge=1, le=9999)
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=32)
    current_address: str = Field(min_length=1, max_length=512)
    permanent_address: str | None = Field(default=None, max_length=512)
    status: int | None = Field(default=None, ge=0, le=1)


class PeopleStatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = Field(ge=0, le=1)


class GuardianLinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parent_id: int = Field(ge=1)
    relationship: str = Field(min_length=1, max_length=32)
    is_primary: bool | None = None


class ParentStudentLinkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: int = Field(ge=1)
    relationship: str = Field(min_length=1, max_length=32)


class ParentCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    mobile: str = Field(min_length=7, max_length=32)
    current_address: str | None = Field(default=None, max_length=512)
    occupation: str | None = Field(default=None, max_length=255)
    status: int | None = Field(default=1, ge=0, le=1)
    students: list[ParentStudentLinkBody] = Field(default_factory=list)


class ParentUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    mobile: str = Field(min_length=7, max_length=32)
    current_address: str | None = Field(default=None, max_length=512)
    occupation: str | None = Field(default=None, max_length=255)
    status: int | None = Field(default=None, ge=0, le=1)


class TimetableEntryCreateBody(BaseModel):
    """Create a class timetable period. school_id is never accepted."""

    model_config = ConfigDict(extra="forbid")

    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    teacher_user_id: int = Field(ge=1)
    day: str = Field(min_length=1, max_length=16)
    start_time: str = Field(min_length=4, max_length=8)
    end_time: str = Field(min_length=4, max_length=8)
    note: str | None = Field(default=None, max_length=512)


class TimetableEntryUpdateBody(BaseModel):
    """Partial timetable update. school_id is never accepted."""

    model_config = ConfigDict(extra="forbid")

    session_year_id: int | None = Field(default=None, ge=1)
    class_section_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    teacher_user_id: int | None = Field(default=None, ge=1)
    day: str | None = Field(default=None, min_length=1, max_length=16)
    start_time: str | None = Field(default=None, min_length=4, max_length=8)
    end_time: str | None = Field(default=None, min_length=4, max_length=8)
    note: str | None = Field(default=None, max_length=512)


class HomeworkAttachmentMeta(BaseModel):
    """Client-declared attachment metadata only (no storage_key/path)."""

    model_config = ConfigDict(extra="forbid")

    original_filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=128)
    size_bytes: int = Field(ge=0, le=26214400)


class HomeworkCreateBody(BaseModel):
    """Create homework. school_id / evaluation fields never accepted.

    Late policy is per-homework via ``allow_late`` (no school-wide settings model).
    """

    model_config = ConfigDict(extra="forbid")

    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    teacher_user_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=20000)
    assigned_date: date
    deadline_at: datetime
    max_marks: float | None = Field(default=None, ge=0)
    # Per-homework only — there is no school_settings late-rules ORM.
    allow_late: bool = True
    attachments: list[HomeworkAttachmentMeta] = Field(default_factory=list)


class HomeworkUpdateBody(BaseModel):
    """Partial homework update. school_id never accepted."""

    model_config = ConfigDict(extra="forbid")

    session_year_id: int | None = Field(default=None, ge=1)
    class_section_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    teacher_user_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=20000)
    assigned_date: date | None = None
    deadline_at: datetime | None = None
    max_marks: float | None = Field(default=None, ge=0)
    allow_late: bool | None = None
    attachments: list[HomeworkAttachmentMeta] | None = None


class HomeworkEvaluationBody(BaseModel):
    """Teacher evaluation. Status/timestamps set server-side."""

    model_config = ConfigDict(extra="forbid")

    marks: float | None = Field(default=None, ge=0)
    grade: str | None = Field(default=None, max_length=64)
    feedback: str | None = Field(default=None, max_length=20000)


def _homework_write_body(body) -> dict[str, Any]:
    """Keep teacher_user_id; strip ownership / evaluation smuggling."""
    data = body.model_dump(exclude_unset=True)
    return homework_svc.sanitize_homework_body(data)


def _school_id(auth: AuthContext) -> int:
    return int(auth.user.school_id)  # type: ignore[arg-type]


def _run(action):
    try:
        return action()
    except academics.AcademicError as exc:
        # Fixed service messages only — never leak SQL / IntegrityError text.
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def _write_body(body) -> dict:
    return academics.sanitize_write_body(body.model_dump(exclude_unset=True))


def _timetable_write_body(body) -> dict:
    """Like sanitize_write_body but keeps teacher_user_id (blocked for other resources)."""
    data = body.model_dump(exclude_unset=True)
    for key in ("school_id", "id", "deleted_at", "created_at", "updated_at", "staff_id"):
        data.pop(key, None)
    return data


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


@router.get("/me", response_model=UserResponse)
def school_admin_me(auth: Annotated[AuthContext, Depends(require_school_context)]) -> UserResponse:
    return UserResponse.model_validate(auth.user)


@router.get("/school", response_model=SchoolResponse)
def school_admin_own_school(
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    """Return the school bound to the authenticated School Admin (server-side school_id)."""
    try:
        school = school_service.get_school(db, auth.user.school_id)  # type: ignore[arg-type]
    except school_service.SchoolServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SchoolResponse.model_validate(school)


@router.get("/sessions")
def school_admin_sessions(
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Session years for the signed-in school only."""
    school_id = auth.user.school_id
    rows = db.scalars(
        select(SessionYear)
        .where(SessionYear.school_id == school_id, SessionYear.deleted_at.is_(None))
        .order_by(SessionYear.start_date.desc())
    )
    return {
        "items": [
            {"id": row.id, "name": row.name, "default": row.default}
            for row in rows
        ]
    }


# --- Phase 4: Class Management (direct /school-admin/classes) ---
# Compatibility: equivalent academics/classes routes remain for existing clients.


@router.get("/classes")
def list_classes(
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    medium_id: int | None = Query(default=None, ge=1),
) -> dict:
    """List classes for the signed-in school. Soft-deleted rows are excluded."""
    return _run(
        lambda: academics.list_classes(
            db, _school_id(auth), q, page, page_size, medium_id=medium_id
        )
    )


@router.post("/classes", status_code=status.HTTP_201_CREATED)
def create_class(
    body: ClassWriteBody,
    auth: Annotated[AuthContext, Depends(require_structure_write)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Create a class. School ownership comes from auth, never from the body."""
    return _run(lambda: academics.create_class(db, _school_id(auth), _write_body(body)))


@router.get("/classes/{class_id}")
def get_class(
    class_id: int,
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Class detail with linked sections and subjects for this school only."""
    return _run(lambda: academics.get_class(db, _school_id(auth), class_id))


@router.patch("/classes/{class_id}")
def update_class(
    class_id: int,
    body: ClassWriteBody,
    auth: Annotated[AuthContext, Depends(require_structure_write)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Partial update. Does not cascade-delete sections or subjects."""
    return _run(
        lambda: academics.update_class(
            db, _school_id(auth), class_id, _write_body(body)
        )
    )


# --- Phase 5: Section Management (direct /school-admin/sections) ---
# Sections are school-scoped; class association uses class_sections.
# Compatibility: academics/sections (name-only create) remains.


@router.get("/sections")
def list_sections(
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    class_id: int | None = Query(default=None, ge=1),
) -> dict:
    """List sections for the signed-in school. Optional class_id filters via class_sections."""
    return _run(
        lambda: academics.list_sections(
            db, _school_id(auth), q, page, page_size, class_id=class_id
        )
    )


@router.post("/sections", status_code=status.HTTP_201_CREATED)
def create_section(
    body: SectionWriteBody,
    auth: Annotated[AuthContext, Depends(require_structure_write)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Create/reuse a school section and link it to a class. school_id from auth only."""
    return _run(
        lambda: academics.create_section_for_class(
            db, _school_id(auth), _write_body(body)
        )
    )


@router.get("/sections/{section_id}")
def get_section(
    section_id: int,
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Section detail with linked classes for this school only."""
    return _run(lambda: academics.get_section(db, _school_id(auth), section_id))


@router.patch("/sections/{section_id}")
def update_section(
    section_id: int,
    body: SectionWriteBody,
    auth: Annotated[AuthContext, Depends(require_structure_write)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Partial update. Does not cascade-delete classes or other academic records."""
    return _run(
        lambda: academics.update_section(
            db, _school_id(auth), section_id, _write_body(body)
        )
    )


# --- Phase 6: Subject Management (direct /school-admin/subjects) ---
# Class association uses class_subjects. Academics /subjects and /class-subjects remain.


@router.get("/subjects")
def list_subjects(
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    medium_id: int | None = Query(default=None, ge=1),
    class_id: int | None = Query(default=None, ge=1),
) -> dict:
    """List subjects for the signed-in school. Soft-deleted rows are excluded."""
    return _run(
        lambda: academics.list_subjects(
            db,
            _school_id(auth),
            q,
            page,
            page_size,
            medium_id=medium_id,
            class_id=class_id,
        )
    )


@router.post("/subjects", status_code=status.HTTP_201_CREATED)
def create_subject(
    body: SubjectWriteBody,
    auth: Annotated[AuthContext, Depends(require_structure_write)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Create a subject. School ownership comes from auth, never from the body."""
    return _run(
        lambda: academics.create_subject(
            db, _school_id(auth), _write_body(body)
        )
    )


@router.get("/subjects/{subject_id}")
def get_subject(
    subject_id: int,
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Subject detail with active class associations for this school only."""
    return _run(lambda: academics.get_subject(db, _school_id(auth), subject_id))


@router.patch("/subjects/{subject_id}")
def update_subject(
    subject_id: int,
    body: SubjectWriteBody,
    auth: Annotated[AuthContext, Depends(require_structure_write)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Partial update. Does not change class_subjects mappings."""
    return _run(
        lambda: academics.update_subject(
            db, _school_id(auth), subject_id, _write_body(body)
        )
    )


@router.get("/subjects/{subject_id}/classes")
def list_subject_classes(
    subject_id: int,
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> dict:
    """Active classes linked to this subject via class_subjects."""
    return _run(
        lambda: academics.list_subject_classes(
            db, _school_id(auth), subject_id, page, page_size
        )
    )


@router.put("/subjects/{subject_id}/classes")
def replace_subject_classes(
    subject_id: int,
    body: SubjectClassesBody,
    auth: Annotated[AuthContext, Depends(require_structure_write)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Replace active class associations (soft-delete removed links; revive historical)."""
    return _run(
        lambda: academics.replace_subject_classes(
            db, _school_id(auth), subject_id, body.class_ids
        )
    )


# --- Module 3: Teacher & Staff Management ---


# --- People API: students / parents (keeps /academics/... for compatibility) ---


@router.get("/students")
def list_people_students(
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: int | None = Query(default=None, alias="status", ge=0, le=1),
    session_year_id: int | None = Query(default=None, ge=1),
    class_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    parent_id: int | None = Query(default=None, ge=1),
    sort: str = Query(default="name"),
    order: str = Query(default="asc"),
) -> dict:
    return _run(
        lambda: people_svc.list_students(
            db,
            _school_id(auth),
            q=q,
            page=page,
            page_size=page_size,
            status=status_filter,
            session_year_id=session_year_id,
            class_id=class_id,
            class_section_id=class_section_id,
            parent_id=parent_id,
            sort=sort,
            order=order,
        )
    )


@router.post("/students", status_code=status.HTTP_201_CREATED)
def create_people_student(
    body: StudentCreateBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: people_svc.create_student(db, _school_id(auth), _write_body(body)))


@router.get("/students/{student_id}")
def get_people_student(
    student_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: people_svc.get_student(db, _school_id(auth), student_id))


@router.patch("/students/{student_id}")
def update_people_student(
    student_id: int,
    body: StudentUpdateBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: people_svc.update_student(db, _school_id(auth), student_id, _write_body(body))
    )


@router.patch("/students/{student_id}/status")
def update_people_student_status(
    student_id: int,
    body: PeopleStatusBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: people_svc.update_student_status(db, _school_id(auth), student_id, body.status)
    )


@router.post("/students/{student_id}/guardians")
def link_people_guardian(
    student_id: int,
    body: GuardianLinkBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: people_svc.link_guardian(db, _school_id(auth), student_id, _write_body(body))
    )


@router.delete("/students/{student_id}/guardians/{parent_id}")
def unlink_people_guardian(
    student_id: int,
    parent_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: people_svc.unlink_guardian(db, _school_id(auth), student_id, parent_id)
    )


@router.post("/students/{student_id}/photo", status_code=status.HTTP_201_CREATED)
async def upload_student_photo(
    student_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
    file: UploadFile = File(...),
) -> dict:
    data, filename = await _read_upload(file)
    result = _run(
        lambda: docs_svc.upload_photo(
            db, _school_id(auth), "student", student_id, data=data, filename=filename
        )
    )
    return {"photo_url": result["photo_url"]}


@router.get("/students/{student_id}/photo")
def get_student_photo(
    student_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    data, content_type = _run(
        lambda: docs_svc.get_profile_photo_bytes(db, _school_id(auth), "student", student_id)
    )
    return Response(content=data, media_type=content_type, headers={"X-Content-Type-Options": "nosniff"})


@router.post("/students/{student_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_student_document(
    student_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
    file: UploadFile = File(...),
    title: str = Form(default=""),
    category: str = Form(default="other"),
) -> dict:
    data, filename = await _read_upload(file)
    return _run(
        lambda: docs_svc.upload_document(
            db,
            _school_id(auth),
            "student",
            student_id,
            category=category,
            data=data,
            filename=filename,
            title=title or None,
        )
    )


@router.get("/students/{student_id}/documents")
def list_student_documents(
    student_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    category: str | None = Query(default=None),
) -> dict:
    return _run(
        lambda: docs_svc.list_documents(
            db,
            _school_id(auth),
            "student",
            student_id,
            page=page,
            page_size=page_size,
            category=category,
        )
    )


@router.get("/students/{student_id}/documents/{document_id}")
def get_student_document(
    student_id: int,
    document_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: docs_svc.get_document(
            db, _school_id(auth), "student", student_id, document_id
        )
    )


@router.delete("/students/{student_id}/documents/{document_id}")
def delete_student_document(
    student_id: int,
    document_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: docs_svc.delete_document(
            db, _school_id(auth), "student", student_id, document_id
        )
    )


@router.get("/students/{student_id}/documents/{document_id}/download")
def download_student_document(
    student_id: int,
    document_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    data, content_type, filename = _run(
        lambda: docs_svc.download_document(
            db, _school_id(auth), "student", student_id, document_id
        )
    )
    headers = {"X-Content-Type-Options": "nosniff"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(content=data, media_type=content_type, headers=headers)


@router.get("/parents")
def list_people_parents(
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: int | None = Query(default=None, alias="status", ge=0, le=1),
    email: str | None = Query(default=None),
    mobile: str | None = Query(default=None),
) -> dict:
    return _run(
        lambda: people_svc.list_parents(
            db,
            _school_id(auth),
            q=q,
            page=page,
            page_size=page_size,
            status=status_filter,
            email=email,
            mobile=mobile,
        )
    )


@router.post("/parents", status_code=status.HTTP_201_CREATED)
def create_people_parent(
    body: ParentCreateBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: people_svc.create_parent(db, _school_id(auth), _write_body(body)))


@router.get("/parents/{parent_id}")
def get_people_parent(
    parent_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: people_svc.get_parent(db, _school_id(auth), parent_id))


@router.patch("/parents/{parent_id}")
def update_people_parent(
    parent_id: int,
    body: ParentUpdateBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: people_svc.update_parent(db, _school_id(auth), parent_id, _write_body(body))
    )


@router.patch("/parents/{parent_id}/status")
def update_people_parent_status(
    parent_id: int,
    body: PeopleStatusBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: people_svc.update_parent_status(db, _school_id(auth), parent_id, body.status)
    )


@router.get("/teachers/departments")
def list_teacher_departments(
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: teachers_svc.list_departments(db, _school_id(auth), teachers_only=True))


@router.get("/teachers")
def list_teachers(
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: int | None = Query(
        default=None,
        alias="status",
        ge=0,
        le=1,
        description="Account status: 1=active, 0=inactive (User.status).",
    ),
    employment_status: str | None = Query(
        default=None, description="active|on_leave|resigned|terminated (Staff.employment_status)."
    ),
    department: str | None = Query(default=None, max_length=128),
    designation: str | None = Query(default=None, max_length=128),
) -> dict:
    return _run(
        lambda: teachers_svc.list_teachers(
            db,
            _school_id(auth),
            q,
            page,
            page_size,
            status=status_filter,
            employment_status=employment_status,
            department=department,
            designation=designation,
        )
    )


@router.post("/teachers", status_code=status.HTTP_201_CREATED)
def create_teacher(
    body: TeacherCreateBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: teachers_svc.create_teacher(db, _school_id(auth), _write_body(body))
    )


@router.get("/teachers/{teacher_id}")
def get_teacher(
    teacher_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: teachers_svc.get_teacher(db, _school_id(auth), teacher_id))


@router.patch("/teachers/{teacher_id}")
def update_teacher(
    teacher_id: int,
    body: TeacherUpdateBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: teachers_svc.update_teacher(
            db, _school_id(auth), teacher_id, _write_body(body)
        )
    )


@router.patch("/teachers/{teacher_id}/status")
def update_teacher_status(
    teacher_id: int,
    body: TeacherStatusBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: teachers_svc.update_teacher_status(
            db, _school_id(auth), teacher_id, body.status
        )
    )


@router.post("/teachers/{teacher_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_teacher_document(
    teacher_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    file: UploadFile = File(...),
    category: str = Form(default="other"),
    title: str = Form(default=""),
) -> dict:
    data, filename = await _read_upload(file)
    return _run(
        lambda: docs_svc.upload_document(
            db,
            _school_id(auth),
            "teacher",
            teacher_id,
            category=category,
            data=data,
            filename=filename,
            title=title or None,
        )
    )


@router.get("/teachers/{teacher_id}/documents")
def list_teacher_documents(
    teacher_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    category: str | None = Query(default=None),
) -> dict:
    return _run(
        lambda: docs_svc.list_documents(
            db,
            _school_id(auth),
            "teacher",
            teacher_id,
            page=page,
            page_size=page_size,
            category=category,
        )
    )


@router.get("/teachers/{teacher_id}/documents/{document_id}")
def get_teacher_document(
    teacher_id: int,
    document_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: docs_svc.get_document(
            db, _school_id(auth), "teacher", teacher_id, document_id
        )
    )


@router.get("/teachers/{teacher_id}/documents/{document_id}/download")
def download_teacher_document(
    teacher_id: int,
    document_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> Response:
    data, content_type, filename = _run(
        lambda: docs_svc.download_document(
            db, _school_id(auth), "teacher", teacher_id, document_id
        )
    )
    headers = {}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(content=data, media_type=content_type, headers=headers)


@router.delete("/teachers/{teacher_id}/documents/{document_id}")
def delete_teacher_document(
    teacher_id: int,
    document_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: docs_svc.delete_document(
            db, _school_id(auth), "teacher", teacher_id, document_id
        )
    )


@router.post("/teachers/{teacher_id}/photo", status_code=status.HTTP_201_CREATED)
async def upload_teacher_photo(
    teacher_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    file: UploadFile = File(...),
) -> dict:
    data, filename = await _read_upload(file)
    result = _run(
        lambda: docs_svc.upload_photo(
            db, _school_id(auth), "teacher", teacher_id, data=data, filename=filename
        )
    )
    return {"photo_url": result["photo_url"]}


@router.get("/teachers/{teacher_id}/photo")
def get_teacher_photo(
    teacher_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> Response:
    data, content_type = _run(
        lambda: docs_svc.get_profile_photo_bytes(
            db, _school_id(auth), "teacher", teacher_id
        )
    )
    return Response(content=data, media_type=content_type)


# --- Module 2: Teacher timetable views (read-only; writes stay on /timetable-entries) ---
# Static suffixes registered before bare /timetable for clarity.


@router.get("/teachers/{teacher_user_id}/timetable/daily")
def get_teacher_daily_timetable(
    teacher_user_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    session_year_id: int = Query(ge=1),
    day: str = Query(min_length=1, max_length=16),
) -> dict:
    return _run(
        lambda: timetable_svc.teacher_daily_timetable(
            db,
            _school_id(auth),
            teacher_user_id,
            session_year_id=session_year_id,
            day=day,
        )
    )


@router.get("/teachers/{teacher_user_id}/timetable/weekly")
def get_teacher_weekly_timetable(
    teacher_user_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    session_year_id: int = Query(ge=1),
) -> dict:
    return _run(
        lambda: timetable_svc.teacher_weekly_timetable(
            db,
            _school_id(auth),
            teacher_user_id,
            session_year_id=session_year_id,
        )
    )


@router.get("/teachers/{teacher_user_id}/timetable")
def get_teacher_timetable(
    teacher_user_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    session_year_id: int = Query(ge=1),
    day: str | None = Query(default=None, max_length=16),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> dict:
    return _run(
        lambda: timetable_svc.list_teacher_timetable(
            db,
            _school_id(auth),
            teacher_user_id,
            session_year_id=session_year_id,
            day=day,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/teachers/{teacher_user_id}/availability")
def get_teacher_availability(
    teacher_user_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    session_year_id: int = Query(ge=1),
    day: str = Query(min_length=1, max_length=16),
    start_time: str = Query(min_length=4, max_length=8),
    end_time: str = Query(min_length=4, max_length=8),
    exclude_entry_id: int | None = Query(default=None, ge=1),
) -> dict:
    return _run(
        lambda: timetable_svc.check_teacher_availability(
            db,
            _school_id(auth),
            teacher_user_id,
            session_year_id=session_year_id,
            day=day,
            start_time=start_time,
            end_time=end_time,
            exclude_entry_id=exclude_entry_id,
        )
    )


@router.get("/staff/departments")
def list_staff_departments(
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: staff_svc.list_departments(db, _school_id(auth)))


@router.get("/staff")
def list_staff(
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: int | None = Query(default=None, alias="status", ge=0, le=1),
    employment_status: str | None = Query(default=None),
    department: str | None = Query(default=None, max_length=128),
    designation: str | None = Query(default=None, max_length=128),
    role: str | None = Query(
        default=None, description="Optional; only Staff is valid for this endpoint."
    ),
) -> dict:
    return _run(
        lambda: staff_svc.list_staff(
            db,
            _school_id(auth),
            q,
            page,
            page_size,
            status=status_filter,
            employment_status=employment_status,
            department=department,
            designation=designation,
            role=role,
        )
    )


@router.post("/staff", status_code=status.HTTP_201_CREATED)
def create_staff(
    body: StaffCreateBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: staff_svc.create_staff(db, _school_id(auth), _write_body(body)))


@router.get("/staff/{staff_id}")
def get_staff(
    staff_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: staff_svc.get_staff(db, _school_id(auth), staff_id))


@router.patch("/staff/{staff_id}")
def update_staff(
    staff_id: int,
    body: StaffUpdateBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: staff_svc.update_staff(db, _school_id(auth), staff_id, _write_body(body))
    )


@router.patch("/staff/{staff_id}/status")
def update_staff_status(
    staff_id: int,
    body: StaffStatusBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: staff_svc.update_staff_status(db, _school_id(auth), staff_id, body.status)
    )


@router.post("/staff/{staff_id}/documents", status_code=status.HTTP_201_CREATED)
async def upload_staff_document(
    staff_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
    file: UploadFile = File(...),
    category: str = Form(default="other"),
    title: str = Form(default=""),
) -> dict:
    data, filename = await _read_upload(file)
    return _run(
        lambda: docs_svc.upload_document(
            db,
            _school_id(auth),
            "staff",
            staff_id,
            category=category,
            data=data,
            filename=filename,
            title=title or None,
        )
    )


@router.get("/staff/{staff_id}/documents")
def list_staff_documents(
    staff_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    category: str | None = Query(default=None),
) -> dict:
    return _run(
        lambda: docs_svc.list_documents(
            db,
            _school_id(auth),
            "staff",
            staff_id,
            page=page,
            page_size=page_size,
            category=category,
        )
    )


@router.get("/staff/{staff_id}/documents/{document_id}")
def get_staff_document(
    staff_id: int,
    document_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: docs_svc.get_document(
            db, _school_id(auth), "staff", staff_id, document_id
        )
    )


@router.get("/staff/{staff_id}/documents/{document_id}/download")
def download_staff_document(
    staff_id: int,
    document_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
) -> Response:
    data, content_type, filename = _run(
        lambda: docs_svc.download_document(
            db, _school_id(auth), "staff", staff_id, document_id
        )
    )
    headers = {}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return Response(content=data, media_type=content_type, headers=headers)


@router.delete("/staff/{staff_id}/documents/{document_id}")
def delete_staff_document(
    staff_id: int,
    document_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: docs_svc.delete_document(
            db, _school_id(auth), "staff", staff_id, document_id
        )
    )


@router.post("/staff/{staff_id}/photo", status_code=status.HTTP_201_CREATED)
async def upload_staff_photo(
    staff_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
    file: UploadFile = File(...),
) -> dict:
    data, filename = await _read_upload(file)
    result = _run(
        lambda: docs_svc.upload_photo(
            db, _school_id(auth), "staff", staff_id, data=data, filename=filename
        )
    )
    return {"photo_url": result["photo_url"]}


@router.get("/staff/{staff_id}/photo")
def get_staff_photo(
    staff_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
) -> Response:
    data, content_type = _run(
        lambda: docs_svc.get_profile_photo_bytes(db, _school_id(auth), "staff", staff_id)
    )
    return Response(content=data, media_type=content_type)


@router.get("/people")
def list_people(
    auth: Annotated[AuthContext, Depends(require_teachers_or_staff)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    role: str = Query(default="all", description="teacher|staff|all"),
    status_filter: int | None = Query(default=None, alias="status", ge=0, le=1),
    employment_status: str | None = Query(default=None),
    department: str | None = Query(default=None, max_length=128),
    designation: str | None = Query(default=None, max_length=128),
) -> dict:
    return _run(
        lambda: staff_svc.list_people(
            db,
            _school_id(auth),
            q,
            page,
            page_size,
            role=role,
            status=status_filter,
            employment_status=employment_status,
            department=department,
            designation=designation,
        )
    )


# --- Module 1: Class Timetable (direct /school-admin/timetable*) ---
# Permission: teachers.manage. Classroom scheduling deferred (no classroom entity).


@router.get("/timetable/weekly")
def get_weekly_timetable(
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    session_year_id: int = Query(ge=1),
    class_section_id: int = Query(ge=1),
) -> dict:
    """Monday–Saturday weekly view for one class-section and session."""
    return _run(
        lambda: timetable_svc.weekly_timetable(
            db,
            _school_id(auth),
            session_year_id=session_year_id,
            class_section_id=class_section_id,
        )
    )


@router.get("/timetable-entries")
def list_timetable_entries(
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session_year_id: int | None = Query(default=None, ge=1),
    class_id: int | None = Query(default=None, ge=1),
    section_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    day: str | None = Query(default=None, max_length=16),
) -> dict:
    return _run(
        lambda: timetable_svc.list_entries(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            session_year_id=session_year_id,
            class_id=class_id,
            section_id=section_id,
            class_section_id=class_section_id,
            day=day,
        )
    )


@router.post("/timetable-entries", status_code=status.HTTP_201_CREATED)
def create_timetable_entry(
    body: TimetableEntryCreateBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: timetable_svc.create_entry(
            db, _school_id(auth), _timetable_write_body(body)
        )
    )


@router.get("/timetable-entries/{entry_id}")
def get_timetable_entry(
    entry_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: timetable_svc.get_entry(db, _school_id(auth), entry_id))


@router.patch("/timetable-entries/{entry_id}")
def update_timetable_entry(
    entry_id: int,
    body: TimetableEntryUpdateBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: timetable_svc.update_entry(
            db, _school_id(auth), entry_id, _timetable_write_body(body)
        )
    )


@router.delete("/timetable-entries/{entry_id}")
def delete_timetable_entry(
    entry_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: timetable_svc.soft_delete_entry(db, _school_id(auth), entry_id))


# --- Phase 7: Teacher–Subject Assignments (direct /school-admin/teacher-assignments) ---
# Reuses TeacherAssignment + ClassSection. Academics paths remain for compatibility.


@router.get("/teacher-assignments")
def list_teacher_assignments(
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    teacher_id: int | None = Query(default=None, ge=1),
    class_id: int | None = Query(default=None, ge=1),
    section_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    session_id: int | None = Query(default=None, ge=1),
) -> dict:
    """List active teacher assignments for the signed-in school."""
    return _run(
        lambda: academics.list_teacher_assignments(
            db,
            _school_id(auth),
            page,
            page_size,
            teacher_id=teacher_id,
            class_id=class_id,
            section_id=section_id,
            subject_id=subject_id,
            session_id=session_id,
        )
    )


@router.post("/teacher-assignments", status_code=status.HTTP_201_CREATED)
def create_teacher_assignment(
    body: TeacherAssignmentWriteBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Create a teacher–subject assignment. School id comes from auth only."""
    return _run(
        lambda: academics.create_teacher_assignment(
            db, _school_id(auth), _write_body(body)
        )
    )


@router.get("/teacher-assignments/{assignment_id}")
def get_teacher_assignment(
    assignment_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: academics.get_teacher_assignment(db, _school_id(auth), assignment_id))


@router.patch("/teacher-assignments/{assignment_id}")
def update_teacher_assignment(
    assignment_id: int,
    body: TeacherAssignmentWriteBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Partial update. Revalidates the full resulting combination."""
    return _run(
        lambda: academics.update_teacher_assignment(
            db, _school_id(auth), assignment_id, _write_body(body)
        )
    )


@router.delete("/teacher-assignments/{assignment_id}")
def delete_teacher_assignment(
    assignment_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Soft-delete. Historical rows kept; no cascade to attendance/exams."""
    return _run(
        lambda: academics.soft_delete_teacher_assignment(db, _school_id(auth), assignment_id)
    )


@router.get("/schools/{school_id}", response_model=SchoolResponse)
def school_admin_school_by_id(
    school_id: int,
    auth: Annotated[AuthContext, Depends(require_school_context)],
    db: Annotated[Session, Depends(central_db)],
) -> SchoolResponse:
    """School data only when school_id matches auth.user.school_id (tenant isolation)."""
    assert_school_scope(auth, school_id)
    try:
        school = school_service.get_school(db, school_id)
    except school_service.SchoolServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return SchoolResponse.model_validate(school)


# --- Module 3: Homework & Assignment Management ---
# Permission: teachers.manage (same as timetable / teacher-assignments).
# Student submit/list APIs live under /api/student/homework* (legacy student auth).


@router.post("/homework", status_code=status.HTTP_201_CREATED)
def create_homework(
    body: HomeworkCreateBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: homework_svc.create_homework(db, _school_id(auth), _homework_write_body(body))
    )


@router.get("/homework")
def list_homework(
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session_year_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    teacher_user_id: int | None = Query(default=None, ge=1),
    q: str = Query(default=""),
) -> dict:
    return _run(
        lambda: homework_svc.list_homework(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            session_year_id=session_year_id,
            class_section_id=class_section_id,
            subject_id=subject_id,
            teacher_user_id=teacher_user_id,
            q=q,
        )
    )


@router.get("/homework/{homework_id}/submissions")
def list_homework_submissions(
    homework_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    status_filter: str | None = Query(default=None, alias="status"),
    is_late: bool | None = Query(default=None),
) -> dict:
    return _run(
        lambda: homework_svc.list_submissions(
            db,
            _school_id(auth),
            homework_id,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            is_late=is_late,
        )
    )


@router.get("/homework/{homework_id}/summary")
def get_homework_summary(
    homework_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: homework_svc.homework_summary(db, _school_id(auth), homework_id))


@router.get("/homework/{homework_id}")
def get_homework(
    homework_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: homework_svc.get_homework(db, _school_id(auth), homework_id))


@router.patch("/homework/{homework_id}")
def update_homework(
    homework_id: int,
    body: HomeworkUpdateBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: homework_svc.update_homework(
            db, _school_id(auth), homework_id, _homework_write_body(body)
        )
    )


@router.delete("/homework/{homework_id}")
def delete_homework(
    homework_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: homework_svc.soft_delete_homework(db, _school_id(auth), homework_id))


@router.post("/homework/{homework_id}/attachments", status_code=status.HTTP_201_CREATED)
async def upload_homework_attachment(
    homework_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    file: UploadFile = File(...),
) -> dict:
    """Binary attachment upload when DOCUMENT_STORAGE_* is configured; else 503."""
    data, filename = await _read_upload(file)
    return _run(
        lambda: homework_svc.append_stored_attachment_to_homework(
            db,
            _school_id(auth),
            homework_id,
            file_bytes=data,
            claimed_filename=filename or file.filename,
        )
    )


@router.get("/homework-submissions/{submission_id}")
def get_homework_submission(
    submission_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: homework_svc.get_submission(db, _school_id(auth), submission_id))


@router.patch("/homework-submissions/{submission_id}/evaluation")
def evaluate_homework_submission(
    submission_id: int,
    body: HomeworkEvaluationBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: homework_svc.evaluate_submission(
            db,
            _school_id(auth),
            submission_id,
            body.model_dump(exclude_unset=True),
            evaluator_user_id=str(auth.user.id),
        )
    )


# --- Module 4: Study Material Management ---
# Permission: teachers.manage. Binary files require document_storage.
# Chapter/topic are optional free-text (no LessonTopic Neon ORM).


class StudyMaterialCreateBody(BaseModel):
    """JSON create for video_link / document_reference. Files use …/upload."""

    model_config = ConfigDict(extra="forbid")

    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    teacher_user_id: int = Field(ge=1)
    resource_type: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    chapter: str | None = Field(default=None, max_length=255)
    topic: str | None = Field(default=None, max_length=255)
    external_url: str | None = Field(default=None, max_length=2048)


class StudyMaterialUpdateBody(BaseModel):
    """Metadata update. school_id / storage_key never accepted. File replace via …/file."""

    model_config = ConfigDict(extra="forbid")

    session_year_id: int | None = Field(default=None, ge=1)
    class_section_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    teacher_user_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=20000)
    chapter: str | None = Field(default=None, max_length=255)
    topic: str | None = Field(default=None, max_length=255)
    external_url: str | None = Field(default=None, max_length=2048)


def _material_write_body(body) -> dict[str, Any]:
    return materials_svc.sanitize_material_body(body.model_dump(exclude_unset=True))


def _download_response(data: bytes, content_type: str, filename: str | None) -> Response:
    from urllib.parse import quote

    safe_name = (filename or "download").replace('"', "")
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_name}"; filename*=UTF-8\'\'{quote(safe_name)}',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
    return Response(content=data, media_type=content_type, headers=headers)


@router.post("/study-materials", status_code=status.HTTP_201_CREATED)
def create_study_material(
    body: StudyMaterialCreateBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    """Create video_link or document_reference. For files use POST …/study-materials/upload."""
    payload = _material_write_body(body)
    if str(payload.get("resource_type") or "").lower() == "file":
        raise HTTPException(
            status_code=422,
            detail="resource_type=file requires multipart upload at POST /study-materials/upload",
        )
    return _run(
        lambda: materials_svc.create_material(
            db,
            _school_id(auth),
            payload,
            actor_v1_user_id=str(auth.user.id),
        )
    )


@router.post("/study-materials/upload", status_code=status.HTTP_201_CREATED)
async def upload_study_material(
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    session_year_id: int = Form(...),
    class_section_id: int = Form(...),
    subject_id: int = Form(...),
    teacher_user_id: int = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    chapter: str | None = Form(default=None),
    topic: str | None = Form(default=None),
) -> dict:
    """Binary study-material upload (PDF/image/DOC/DOCX). Requires document_storage."""
    data, filename = await _read_upload(file)
    body = {
        "session_year_id": session_year_id,
        "class_section_id": class_section_id,
        "subject_id": subject_id,
        "teacher_user_id": teacher_user_id,
        "resource_type": "file",
        "title": title,
        "description": description,
        "chapter": chapter,
        "topic": topic,
    }
    return _run(
        lambda: materials_svc.create_material(
            db,
            _school_id(auth),
            materials_svc.sanitize_material_body(body),
            actor_v1_user_id=str(auth.user.id),
            file_bytes=data,
            claimed_filename=filename or file.filename,
        )
    )


@router.get("/study-materials")
def list_study_materials(
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session_year_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    teacher_user_id: int | None = Query(default=None, ge=1),
    resource_type: str | None = Query(default=None),
    chapter: str | None = Query(default=None),
    topic: str | None = Query(default=None),
    q: str = Query(default=""),
) -> dict:
    return _run(
        lambda: materials_svc.list_materials(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            session_year_id=session_year_id,
            class_section_id=class_section_id,
            subject_id=subject_id,
            teacher_user_id=teacher_user_id,
            resource_type=resource_type,
            chapter=chapter,
            topic=topic,
            q=q,
        )
    )


@router.get("/study-materials/{material_id}")
def get_study_material(
    material_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: materials_svc.get_material(db, _school_id(auth), material_id))


@router.get("/study-materials/{material_id}/download")
def download_study_material(
    material_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> Response:
    data, content_type, filename = _run(
        lambda: materials_svc.get_file_bytes(db, _school_id(auth), material_id)
    )
    return _download_response(data, content_type, filename)


@router.patch("/study-materials/{material_id}")
def update_study_material(
    material_id: int,
    body: StudyMaterialUpdateBody,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: materials_svc.update_material(
            db,
            _school_id(auth),
            material_id,
            _material_write_body(body),
            actor_v1_user_id=str(auth.user.id),
        )
    )


@router.post("/study-materials/{material_id}/file")
async def replace_study_material_file(
    material_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
    file: UploadFile = File(...),
) -> dict:
    data, filename = await _read_upload(file)
    return _run(
        lambda: materials_svc.update_material(
            db,
            _school_id(auth),
            material_id,
            {},
            actor_v1_user_id=str(auth.user.id),
            file_bytes=data,
            claimed_filename=filename or file.filename,
        )
    )


@router.delete("/study-materials/{material_id}")
def delete_study_material(
    material_id: int,
    auth: Annotated[AuthContext, Depends(require_teachers)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: materials_svc.soft_delete_material(db, _school_id(auth), material_id))


# --- Module 5: Online Examination (MCQ assessments) ---
# Permission: exams.manage. Distinct from legacy offline /academics/exams.


class OnlineAssessmentCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    subject_id: int = Field(ge=1)
    teacher_user_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=20000)
    duration_minutes: int = Field(ge=1, le=600)
    total_marks: float = Field(gt=0)
    passing_marks: float = Field(ge=0)
    available_from: datetime
    available_until: datetime


class OnlineAssessmentUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_year_id: int | None = Field(default=None, ge=1)
    class_section_id: int | None = Field(default=None, ge=1)
    subject_id: int | None = Field(default=None, ge=1)
    teacher_user_id: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=20000)
    duration_minutes: int | None = Field(default=None, ge=1, le=600)
    total_marks: float | None = Field(default=None, gt=0)
    passing_marks: float | None = Field(default=None, ge=0)
    available_from: datetime | None = None
    available_until: datetime | None = None
    status: str | None = Field(default=None, max_length=32)
    results_published: bool | None = None


class OnlineAssessmentChoiceBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    choice_text: str = Field(min_length=1, max_length=2000)
    is_correct: bool = False


class OnlineAssessmentQuestionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_text: str = Field(min_length=1, max_length=10000)
    marks: float = Field(gt=0)
    topic: str | None = Field(default=None, max_length=255)
    sort_order: int = 0
    choices: list[OnlineAssessmentChoiceBody] = Field(min_length=2, max_length=8)


class OnlineAssessmentBulkImportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OnlineAssessmentQuestionBody] = Field(min_length=1, max_length=100)


@router.post("/online-assessments", status_code=status.HTTP_201_CREATED)
def create_online_assessment(
    body: OnlineAssessmentCreateBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: oa_svc.create_assessment(
            db, _school_id(auth), oa_svc.sanitize_assessment_body(body.model_dump())
        )
    )


@router.get("/online-assessments")
def list_online_assessments(
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session_year_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    status_filter: str | None = Query(default=None, alias="status"),
    q: str = Query(default=""),
) -> dict:
    return _run(
        lambda: oa_svc.list_assessments(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            session_year_id=session_year_id,
            class_section_id=class_section_id,
            subject_id=subject_id,
            status=status_filter,
            q=q,
        )
    )


@router.get("/online-assessments/{assessment_id}")
def get_online_assessment(
    assessment_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: oa_svc.get_assessment(db, _school_id(auth), assessment_id))


@router.patch("/online-assessments/{assessment_id}")
def update_online_assessment(
    assessment_id: int,
    body: OnlineAssessmentUpdateBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: oa_svc.update_assessment(
            db,
            _school_id(auth),
            assessment_id,
            oa_svc.sanitize_assessment_body(body.model_dump(exclude_unset=True)),
        )
    )


@router.delete("/online-assessments/{assessment_id}")
def delete_online_assessment(
    assessment_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: oa_svc.soft_delete_assessment(db, _school_id(auth), assessment_id))


@router.post("/online-assessments/{assessment_id}/questions", status_code=status.HTTP_201_CREATED)
def add_online_assessment_question(
    assessment_id: int,
    body: OnlineAssessmentQuestionBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: oa_svc.add_question(
            db, _school_id(auth), assessment_id, body.model_dump()
        )
    )


@router.post("/online-assessments/{assessment_id}/questions/import", status_code=status.HTTP_201_CREATED)
def import_online_assessment_questions(
    assessment_id: int,
    body: OnlineAssessmentBulkImportBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: oa_svc.bulk_import_questions(
            db,
            _school_id(auth),
            assessment_id,
            [item.model_dump() for item in body.items],
        )
    )


@router.patch("/online-assessment-questions/{question_id}")
def update_online_assessment_question(
    question_id: int,
    body: OnlineAssessmentQuestionBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: oa_svc.update_question(db, _school_id(auth), question_id, body.model_dump())
    )


@router.delete("/online-assessment-questions/{question_id}")
def delete_online_assessment_question(
    question_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: oa_svc.soft_delete_question(db, _school_id(auth), question_id))


@router.get("/online-assessments/{assessment_id}/attempts")
def list_online_assessment_attempts(
    assessment_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> dict:
    return _run(
        lambda: oa_svc.list_assessment_attempts(
            db, _school_id(auth), assessment_id, page=page, page_size=page_size
        )
    )


@router.get("/online-assessment-attempts/{attempt_id}")
def get_online_assessment_attempt(
    attempt_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: oa_svc.get_attempt_admin(db, _school_id(auth), attempt_id))


# --- Module 6: Offline Examination, Marks & Results ---
# Permission: exams.manage. Reuses Exam ORM; schedules/marks in offline_exam_* tables.


class OfflineExamCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    session_year_id: int = Field(ge=1)
    class_section_id: int = Field(ge=1)
    exam_type: str | None = Field(default=None, max_length=64)
    exam_date: date | None = None


class OfflineExamUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1024)
    session_year_id: int | None = Field(default=None, ge=1)
    class_section_id: int | None = Field(default=None, ge=1)
    exam_type: str | None = Field(default=None, max_length=64)
    exam_date: date | None = None
    publish: bool | None = None


class OfflineScheduleCreateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_id: int = Field(ge=1)
    class_section_id: int | None = Field(default=None, ge=1)
    teacher_user_id: int | None = Field(default=None, ge=1)
    exam_date: date
    start_time: str | None = Field(default=None, max_length=8)
    end_time: str | None = Field(default=None, max_length=8)
    max_marks: float = Field(gt=0)
    passing_marks: float = Field(ge=0)


class OfflineMarkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: int = Field(ge=1)
    marks_obtained: float | None = Field(default=None, ge=0)
    status: str = Field(default="present", max_length=32)
    reason: str | None = Field(default=None, max_length=512)


class OfflineMarkBulkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OfflineMarkBody] = Field(min_length=1, max_length=200)


@router.post("/offline-exams", status_code=status.HTTP_201_CREATED)
def create_offline_exam(
    body: OfflineExamCreateBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: offline_svc.create_exam(
            db, _school_id(auth), offline_svc.sanitize_body(body.model_dump())
        )
    )


@router.get("/offline-exams")
def list_offline_exams(
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session_year_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    q: str = Query(default=""),
) -> dict:
    return _run(
        lambda: offline_svc.list_exams(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            session_year_id=session_year_id,
            class_section_id=class_section_id,
            q=q,
        )
    )


@router.get("/offline-exams/{exam_id}")
def get_offline_exam(
    exam_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: offline_svc.get_exam(db, _school_id(auth), exam_id))


@router.patch("/offline-exams/{exam_id}")
def update_offline_exam(
    exam_id: int,
    body: OfflineExamUpdateBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: offline_svc.update_exam(
            db,
            _school_id(auth),
            exam_id,
            offline_svc.sanitize_body(body.model_dump(exclude_unset=True)),
        )
    )


@router.delete("/offline-exams/{exam_id}")
def delete_offline_exam(
    exam_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: offline_svc.soft_delete_exam(db, _school_id(auth), exam_id))


@router.post("/offline-exams/{exam_id}/schedules", status_code=status.HTTP_201_CREATED)
def create_offline_exam_schedule(
    exam_id: int,
    body: OfflineScheduleCreateBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(
        lambda: offline_svc.create_schedule(
            db,
            _school_id(auth),
            exam_id,
            offline_svc.sanitize_body(body.model_dump(exclude_unset=True)),
        )
    )


@router.get("/offline-exam-schedules")
def list_offline_exam_schedules(
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    exam_id: int | None = Query(default=None, ge=1),
    session_year_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    exam_date: date | None = Query(default=None),
) -> dict:
    return _run(
        lambda: offline_svc.list_schedules(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            exam_id=exam_id,
            session_year_id=session_year_id,
            class_section_id=class_section_id,
            subject_id=subject_id,
            exam_date=exam_date,
        )
    )


@router.get("/offline-exam-schedules/{schedule_id}")
def get_offline_exam_schedule(
    schedule_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: offline_svc.get_schedule(db, _school_id(auth), schedule_id))


@router.post("/offline-exam-schedules/{schedule_id}/marks", status_code=status.HTTP_201_CREATED)
def upsert_offline_exam_mark(
    schedule_id: int,
    body: OfflineMarkBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    payload = body.model_dump(exclude_unset=True)
    reason = payload.pop("reason", None)
    return _run(
        lambda: offline_svc.upsert_mark(
            db,
            _school_id(auth),
            schedule_id,
            offline_svc.sanitize_body(payload),
            actor_v1_user_id=str(auth.user.id),
            reason=reason,
        )
    )


@router.post("/offline-exam-schedules/{schedule_id}/marks/bulk")
def bulk_offline_exam_marks(
    schedule_id: int,
    body: OfflineMarkBulkBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    items = [offline_svc.sanitize_body(i.model_dump(exclude={"reason"})) for i in body.items]
    return _run(
        lambda: offline_svc.bulk_upsert_marks(
            db,
            _school_id(auth),
            schedule_id,
            items,
            actor_v1_user_id=str(auth.user.id),
        )
    )


@router.get("/offline-exam-marks")
def list_offline_exam_marks(
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    exam_id: int | None = Query(default=None, ge=1),
    schedule_id: int | None = Query(default=None, ge=1),
    student_id: int | None = Query(default=None, ge=1),
) -> dict:
    return _run(
        lambda: offline_svc.list_marks(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            exam_id=exam_id,
            schedule_id=schedule_id,
            student_id=student_id,
        )
    )


@router.get("/offline-exam-marks/{mark_id}/audits")
def list_offline_exam_mark_audits(
    mark_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> list:
    return _run(lambda: offline_svc.list_mark_audits(db, _school_id(auth), mark_id))


@router.post("/offline-exams/{exam_id}/process-results")
def process_offline_exam_results(
    exam_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: offline_svc.process_results(db, _school_id(auth), exam_id))


@router.get("/offline-exams/{exam_id}/results")
def list_offline_exam_results(
    exam_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> dict:
    return _run(
        lambda: offline_svc.list_results(
            db, _school_id(auth), exam_id, page=page, page_size=page_size
        )
    )


@router.get("/offline-exams/{exam_id}/results/summary")
def offline_exam_results_summary(
    exam_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> dict:
    return _run(lambda: offline_svc.class_result_summary(db, _school_id(auth), exam_id))
