"""School Admin self endpoints — scoped by authenticated user.school_id."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, assert_school_scope, require_school_permission
from app.models.tables import SessionYear
from app.schemas.v1.schools import SchoolResponse
from app.schemas.v1.users import UserResponse
from app.api.v1 import school_admin_academics as academics_routes
from app.services.v1 import rbac, school_service
from app.services.v1 import school_academics as academics

router = APIRouter(prefix="/school-admin", tags=["v1-school-admin"])

# Basic school context. Every admin role grants dashboard.view.
require_school_context = require_school_permission(rbac.PERM_DASHBOARD)
require_structure_write = require_school_permission(rbac.PERM_SCHOOL)
# Teacher assignments use teachers.manage (same as academics/teacher-assignments).
require_teachers = require_school_permission(rbac.PERM_TEACHERS)

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
