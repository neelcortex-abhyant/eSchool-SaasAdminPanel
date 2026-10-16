"""School-admin academic CRUD. The school id is taken from the authenticated user."""

from __future__ import annotations
from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_school_admin
from app.models.tables import (
    Announcement,
    Attendance,
    ClassSection,
    Exam,
    Expense,
    Fee,
    Leave,
    Medium,
    SchoolClass,
    Section,
    SessionYear,
    Subject,
)
from app.services.v1 import school_academics as academics

router = APIRouter(prefix="/school-admin/academics", tags=["v1-school-admin-academics"])


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
    session_year_id: int | None = None
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


def _run(action):
    try:
        return action()
    except academics.AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/summary")
def summary(
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
    session_year_id: int | None = None,
):
    return academics.summary(db, _school_id(auth), session_year_id)


@router.get("/{resource}")
def index(
    resource: str,
    auth: Annotated[AuthContext, Depends(require_school_admin)],
    db: Annotated[Session, Depends(central_db)],
    q: str = "",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    school_id = _school_id(auth)

    def load():
        if resource == "students":
            return academics.list_students(db, school_id, q, page, page_size)
        if resource in {"teachers", "parents"}:
            return academics.list_people(db, school_id, resource, q, page, page_size)
        if resource == "classes":
            return academics.list_named(db, SchoolClass, school_id, q, page, page_size, lambda row: {"id": row.id, "name": row.name, "medium_id": row.medium_id})
        if resource == "sections":
            return academics.list_named(db, Section, school_id, q, page, page_size, lambda row: {"id": row.id, "name": row.name})
        if resource == "subjects":
            return academics.list_named(db, Subject, school_id, q, page, page_size, lambda row: {"id": row.id, "name": row.name, "code": row.code, "type": row.type, "medium_id": row.medium_id})
        if resource == "mediums":
            return academics.list_named(db, Medium, school_id, q, page, page_size, lambda row: {"id": row.id, "name": row.name})
        if resource == "sessions":
            return academics.list_named(db, SessionYear, school_id, q, page, page_size, lambda row: {"id": row.id, "name": row.name, "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat()})
        if resource == "class-sections":
            return academics.list_named(db, ClassSection, school_id, "", page, page_size, lambda row: {"id": row.id, "name": f"Class {row.class_id} / Section {row.section_id}", "class_id": row.class_id, "section_id": row.section_id, "medium_id": row.medium_id})
        if resource == "attendances":
            return academics.list_named(db, Attendance, school_id, "", page, page_size, lambda row: {"id": row.id, "name": row.date.isoformat(), "student_id": row.student_id, "type": row.type, "date": row.date.isoformat(), "remark": row.remark})
        if resource == "exams":
            return academics.list_named(db, Exam, school_id, q, page, page_size, lambda row: {"id": row.id, "name": row.name, "class_id": row.class_id, "publish": row.publish})
        if resource == "fees":
            return academics.list_named(db, Fee, school_id, q, page, page_size, lambda row: {"id": row.id, "name": row.name, "due_date": row.due_date.isoformat(), "due_charges": row.due_charges})
        if resource == "expenses":
            return academics.list_named(db, Expense, school_id, "", page, page_size, lambda row: {"id": row.id, "name": row.title, "title": row.title, "amount": row.amount, "date": row.date.isoformat()})
        if resource == "notices":
            return academics.list_named(db, Announcement, school_id, q, page, page_size, lambda row: {"id": row.id, "name": row.title, "title": row.title, "description": row.description})
        if resource == "leaves":
            return academics.list_named(db, Leave, school_id, "", page, page_size, lambda row: {"id": row.id, "name": row.reason, "user_id": row.user_id, "from_date": row.from_date.isoformat(), "to_date": row.to_date.isoformat(), "status": row.status})
        raise academics.AcademicError(404, "Unknown school record")

    return _run(load)


@router.post("/{resource}", status_code=201)
def create(resource: str, body: WriteBody, auth: Annotated[AuthContext, Depends(require_school_admin)], db: Annotated[Session, Depends(central_db)]):
    school_id = _school_id(auth)
    data = body.model_dump(exclude_unset=True)

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
def update(resource: str, row_id: int, body: WriteBody, auth: Annotated[AuthContext, Depends(require_school_admin)], db: Annotated[Session, Depends(central_db)]):
    school_id = _school_id(auth)
    data = body.model_dump(exclude_unset=True)

    def change():
        if resource == "students":
            return academics.update_student(db, school_id, row_id, data)
        models = {
            "classes": SchoolClass,
            "sections": Section,
            "subjects": Subject,
            "mediums": Medium,
            "sessions": SessionYear,
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
        return {"id": row.id, "name": getattr(row, "name", None) or getattr(row, "title", None) or getattr(row, "reason", "")}

    return _run(change)


@router.delete("/{resource}/{row_id}")
def remove(resource: str, row_id: int, auth: Annotated[AuthContext, Depends(require_school_admin)], db: Annotated[Session, Depends(central_db)]):
    school_id = _school_id(auth)
    models = {
        "classes": SchoolClass,
        "sections": Section,
        "subjects": Subject,
        "mediums": Medium,
        "sessions": SessionYear,
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
        model = models.get(resource)
        if model is None:
            raise academics.AcademicError(404, "This record cannot be deleted here")
        academics.soft_delete(db, model, school_id, row_id)
        return {"deleted": True}

    return _run(drop)
