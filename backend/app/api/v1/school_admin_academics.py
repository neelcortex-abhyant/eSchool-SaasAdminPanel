"""School-admin academic CRUD. The school id is taken from the authenticated user."""

from __future__ import annotations

from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, assert_school_permission, require_school_admin
from app.models.tables import (
    Announcement,
    Attendance,
    ClassSection,
    ClassSubject,
    Exam,
    Expense,
    Fee,
    Leave,
    Medium,
    SchoolClass,
    Section,
    SessionYear,
    Subject,
    TeacherAssignment,
)
from app.services.v1 import rbac
from app.services.v1 import school_academics as academics

# Mounted under school_admin.router (/school-admin) so URLs stay
# /api/v1/school-admin/academics/... . Tag is applied by the parent include.
router = APIRouter(prefix="/academics")


class WriteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    title: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    mobile: str | None = Field(default=None, max_length=32)
    qualification: str | None = None
    salary: float | None = None
    admission_no: str | None = None
    roll_number: int | None = None
    admission_date: Date | None = None
    class_section_id: int | None = None
    class_id: int | None = None
    section_id: int | None = None
    subject_id: int | None = None
    teacher_id: int | None = None
    session_year_id: int | None = None
    session_id: int | None = None  # alias for session_year_id on teacher-assignments
    guardian_id: int | None = None
    medium_id: int | None = None
    student_id: int | None = None
    user_id: int | None = None
    start_date: Date | None = None
    end_date: Date | None = None
    from_date: Date | None = None
    to_date: Date | None = None
    due_date: Date | None = None
    due_charges: float | None = None
    amount: float | None = None
    date: Date | None = None
    type: str | int | None = None
    code: str | None = None
    description: str | None = None
    reason: str | None = None
    remark: str | None = None
    publish: int | None = None
    status: int | None = None
    default: int | None = None
    include_semesters: int | None = None


def _school_id(auth: AuthContext) -> int:
    return int(auth.user.school_id)  # type: ignore[arg-type]


# Permission needed for each resource (reads and writes).
RESOURCE_PERMISSIONS = {
    "students": rbac.PERM_STUDENTS,
    "parents": rbac.PERM_STUDENTS,
    "teachers": rbac.PERM_TEACHERS,
    "leaves": rbac.PERM_TEACHERS,
    "exams": rbac.PERM_EXAMS,
    "attendances": rbac.PERM_ATTENDANCE,
    "fees": rbac.PERM_FEES,
    "expenses": rbac.PERM_FEES,
    "notices": rbac.PERM_SCHOOL,
    # Least privilege: teachers.manage (exists). Role catalog was not changed.
    "teacher-assignments": rbac.PERM_TEACHERS,
}
# Academic structure: every role may read it (forms need classes and sessions);
# only school.manage may change it.
STRUCTURE_RESOURCES = frozenset(
    {
        "classes",
        "sections",
        "subjects",
        "mediums",
        "sessions",
        "class-sections",
        "class-subjects",
    }
)


def _allow(auth: AuthContext, db: Session, resource: str, *, write: bool) -> None:
    if resource in STRUCTURE_RESOURCES:
        permission = rbac.PERM_SCHOOL if write else rbac.PERM_DASHBOARD
    else:
        permission = RESOURCE_PERMISSIONS.get(resource)
    if permission is None:
        # Still require a school-admin with dashboard.view before a generic 404.
        assert_school_permission(auth, db, rbac.PERM_DASHBOARD)
        return
    assert_school_permission(auth, db, permission)


def _run(action):
    try:
        return action()
    except academics.AcademicError as exc:
        # Detail is a fixed service string — never pass IntegrityError text through.
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.get("/summary")
def summary(
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
    session_year_id: int | None = None,
):
    assert_school_permission(auth, db, rbac.PERM_DASHBOARD)
    return academics.summary(db, _school_id(auth), session_year_id)


@router.post("/sessions/{session_id}/activate")
def activate_session(
    session_id: int,
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
):
    """Atomically set this session as the school's default and clear other defaults."""
    assert_school_permission(auth, db, rbac.PERM_SCHOOL)
    return _run(lambda: academics.activate_session(db, _school_id(auth), session_id))


@router.get("/sessions/{row_id}")
def get_session(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
):
    assert_school_permission(auth, db, rbac.PERM_DASHBOARD)
    return _run(lambda: academics.get_session(db, _school_id(auth), row_id))


@router.get("/teacher-assignments/{row_id}")
def get_teacher_assignment(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
):
    assert_school_permission(auth, db, rbac.PERM_TEACHERS)
    return _run(lambda: academics.get_teacher_assignment(db, _school_id(auth), row_id))


@router.get("/{resource}")
def index(
    resource: str,
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    medium_id: int | None = Query(default=None, ge=1),
    class_id: int | None = Query(default=None, ge=1),
    subject_id: int | None = Query(default=None, ge=1),
    teacher_id: int | None = Query(default=None, ge=1),
    class_section_id: int | None = Query(default=None, ge=1),
    session_year_id: int | None = Query(default=None, ge=1),
    section_id: int | None = Query(default=None, ge=1),
    session_id: int | None = Query(default=None, ge=1),
):
    _allow(auth, db, resource, write=False)
    school_id = _school_id(auth)

    def load():
        if resource == "students":
            return academics.list_students(db, school_id, q, page, page_size)
        if resource in {"teachers", "parents"}:
            return academics.list_people(db, school_id, resource, q, page, page_size)
        if resource == "classes":
            return academics.list_classes(db, school_id, q, page, page_size, medium_id=medium_id)
        if resource == "sections":
            return academics.list_sections(
                db, school_id, q, page, page_size, class_id=class_id
            )
        if resource == "subjects":
            return academics.list_subjects(
                db, school_id, q, page, page_size, medium_id=medium_id, class_id=class_id
            )
        if resource == "mediums":
            return academics.list_named(
                db, Medium, school_id, q, page, page_size, lambda row: {"id": row.id, "name": row.name}
            )
        if resource == "sessions":
            return academics.list_sessions(db, school_id, q, page, page_size)
        if resource == "class-sections":
            return academics.list_class_sections(
                db, school_id, page, page_size, class_id=class_id, medium_id=medium_id
            )
        if resource == "class-subjects":
            return academics.list_class_subjects(
                db, school_id, page, page_size, class_id=class_id, subject_id=subject_id
            )
        if resource == "teacher-assignments":
            return academics.list_teacher_assignments(
                db,
                school_id,
                page,
                page_size,
                teacher_id=teacher_id,
                subject_id=subject_id,
                class_id=class_id,
                section_id=section_id,
                class_section_id=class_section_id,
                session_id=session_id,
                session_year_id=session_year_id,
            )
        if resource == "attendances":
            return academics.list_named(
                db,
                Attendance,
                school_id,
                "",
                page,
                page_size,
                lambda row: {
                    "id": row.id,
                    "name": row.date.isoformat(),
                    "student_id": row.student_id,
                    "type": row.type,
                    "date": row.date.isoformat(),
                    "remark": row.remark,
                },
            )
        if resource == "exams":
            return academics.list_named(
                db,
                Exam,
                school_id,
                q,
                page,
                page_size,
                lambda row: {
                    "id": row.id,
                    "name": row.name,
                    "class_id": row.class_id,
                    "publish": row.publish,
                },
            )
        if resource == "fees":
            return academics.list_named(
                db,
                Fee,
                school_id,
                q,
                page,
                page_size,
                lambda row: {
                    "id": row.id,
                    "name": row.name,
                    "due_date": row.due_date.isoformat(),
                    "due_charges": row.due_charges,
                },
            )
        if resource == "expenses":
            return academics.list_named(
                db,
                Expense,
                school_id,
                "",
                page,
                page_size,
                lambda row: {
                    "id": row.id,
                    "name": row.title,
                    "title": row.title,
                    "amount": row.amount,
                    "date": row.date.isoformat(),
                },
            )
        if resource == "notices":
            return academics.list_named(
                db,
                Announcement,
                school_id,
                q,
                page,
                page_size,
                lambda row: {
                    "id": row.id,
                    "name": row.title,
                    "title": row.title,
                    "description": row.description,
                },
            )
        if resource == "leaves":
            return academics.list_named(
                db,
                Leave,
                school_id,
                "",
                page,
                page_size,
                lambda row: {
                    "id": row.id,
                    "name": row.reason,
                    "user_id": row.user_id,
                    "from_date": row.from_date.isoformat(),
                    "to_date": row.to_date.isoformat(),
                    "status": row.status,
                },
            )
        raise academics.AcademicError(404, "Unknown school record")

    return _run(load)


@router.post("/{resource}", status_code=201)
def create(
    resource: str,
    body: WriteBody,
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
):
    _allow(auth, db, resource, write=True)
    school_id = _school_id(auth)
    data = academics.sanitize_write_body(body.model_dump(exclude_unset=True))

    def save():
        if resource == "students":
            return academics.create_student(db, school_id, data)
        if resource in {"teachers", "parents"}:
            return academics.create_person(db, school_id, resource, data)
        if resource == "mediums":
            return academics.create_medium(db, school_id, data["name"])
        if resource == "sessions":
            return academics.create_session(db, school_id, data)
        if resource == "sections":
            return academics.create_section(db, school_id, data["name"])
        if resource == "classes":
            return academics.create_class(db, school_id, data)
        if resource == "class-sections":
            return academics.create_class_section(db, school_id, data)
        if resource == "class-subjects":
            return academics.create_class_subject(db, school_id, data)
        if resource == "teacher-assignments":
            return academics.create_teacher_assignment(db, school_id, data)
        if resource == "subjects":
            return academics.create_subject(db, school_id, data)
        if resource == "attendances":
            return academics.create_attendance(db, school_id, data)
        if resource == "exams":
            return academics.create_exam(db, school_id, data)
        if resource == "fees":
            return academics.create_fee(db, school_id, data)
        if resource == "expenses":
            return academics.create_expense(db, school_id, data)
        if resource == "notices":
            return academics.create_announcement(db, school_id, data)
        if resource == "leaves":
            return academics.create_leave(db, school_id, data)
        raise academics.AcademicError(404, "Unknown school record")

    return _run(save)


@router.patch("/{resource}/{row_id}")
def update(
    resource: str,
    row_id: int,
    body: WriteBody,
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
):
    _allow(auth, db, resource, write=True)
    school_id = _school_id(auth)
    data = academics.sanitize_write_body(body.model_dump(exclude_unset=True))

    def change():
        if resource == "students":
            return academics.update_student(db, school_id, row_id, data)
        if resource == "classes":
            return academics.update_class(db, school_id, row_id, data)
        if resource == "sections":
            # Academics PATCH accepts name only; class_id changes use direct section routes.
            return academics.update_section(
                db, school_id, row_id, {k: v for k, v in data.items() if k == "name"}
            )
        if resource == "subjects":
            return academics.update_subject(db, school_id, row_id, data)
        if resource == "class-sections":
            return academics.update_class_section(db, school_id, row_id, data)
        if resource == "class-subjects":
            return academics.update_class_subject(db, school_id, row_id, data)
        if resource == "teacher-assignments":
            return academics.update_teacher_assignment(db, school_id, row_id, data)
        if resource == "sessions":
            return academics.update_session(db, school_id, row_id, data)
        models = {
            "mediums": Medium,
            "exams": Exam,
            "fees": Fee,
            "expenses": Expense,
            "notices": Announcement,
            "leaves": Leave,
        }
        model = models.get(resource)
        if model is None:
            raise academics.AcademicError(404, "This record cannot be edited here")
        row = academics._owned(db, model, row_id, school_id)
        academics.check_references(db, school_id, row, data)
        for key, value in data.items():
            if key in {"id", "school_id"} or not hasattr(row, key):
                continue
            if key == "title" and hasattr(row, "title"):
                row.title = value
            else:
                setattr(row, key, value.strip() if isinstance(value, str) else value)
        if hasattr(row, "updated_at"):
            row.updated_at = academics._now()
        academics._commit(db)
        return {
            "id": row.id,
            "name": getattr(row, "name", None) or getattr(row, "title", None) or getattr(row, "reason", ""),
        }

    return _run(change)


@router.delete("/{resource}/{row_id}")
def remove(
    resource: str,
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
):
    _allow(auth, db, resource, write=True)
    school_id = _school_id(auth)
    models = {
        "classes": SchoolClass,
        "sections": Section,
        "subjects": Subject,
        "mediums": Medium,
        "sessions": SessionYear,
        "class-sections": ClassSection,
        "class-subjects": ClassSubject,
        "teacher-assignments": TeacherAssignment,
        "exams": Exam,
        "fees": Fee,
        "expenses": Expense,
        "notices": Announcement,
        "leaves": Leave,
    }

    def drop():
        if resource == "students":
            academics.delete_student(db, school_id, row_id)
            return {"deleted": True}
        if resource == "sessions":
            academics.soft_delete_session(db, school_id, row_id)
            return {"deleted": True}
        if resource == "teacher-assignments":
            return academics.soft_delete_teacher_assignment(db, school_id, row_id)
        model = models.get(resource)
        if model is None:
            raise academics.AcademicError(404, "This record cannot be deleted here")
        academics.soft_delete(db, model, school_id, row_id)
        return {"deleted": True}

    return _run(drop)
