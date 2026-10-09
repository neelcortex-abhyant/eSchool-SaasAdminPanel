"""Create, update, and delete handlers for admin panel resources."""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.admin import (
    _announcement,
    _attendance,
    _class,
    _exam,
    _expense,
    _fee,
    _guard,
    _leave,
    _package,
    _school,
    _student,
    _subject,
)
from app.api.deps import close_admin_db
from app.core.security import hash_password
from app.models.tables import (
    Announcement,
    Attendance,
    Exam,
    Expense,
    Fee,
    Leave,
    Package,
    School,
    SchoolClass,
    Student,
    Subject,
    User,
)

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _school_id(body_school_id: int | None, actor_school_id: int | None) -> int:
    if actor_school_id is not None:
        if body_school_id is not None and body_school_id != actor_school_id:
            raise HTTPException(status_code=403, detail="Cross-school access denied")
        return actor_school_id
    if body_school_id is None:
        raise HTTPException(status_code=422, detail="school_id is required")
    return body_school_id


def _get_owned(db, model, row_id: int, school_id: int | None):
    row = db.get(model, row_id)
    if row is None or getattr(row, "deleted_at", None) is not None:
        raise HTTPException(status_code=404, detail="Record not found")
    if school_id is not None and getattr(row, "school_id", None) not in (None, school_id):
        raise HTTPException(status_code=403, detail="Cross-school access denied")
    return row


def _touch(row) -> None:
    now = _now()
    if hasattr(row, "updated_at"):
        row.updated_at = now
    if getattr(row, "created_at", None) is None and hasattr(row, "created_at"):
        row.created_at = now


def _remove(db, row) -> None:
    if hasattr(row, "deleted_at"):
        row.deleted_at = _now()
        _touch(row)
    else:
        db.delete(row)
    db.commit()


class StudentWrite(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    admission_no: str = Field(min_length=1, max_length=512)
    class_section_id: int
    session_year_id: int
    guardian_id: int
    admission_date: date
    school_id: int | None = None
    roll_number: int | None = None


class StudentPatch(BaseModel):
    admission_no: str | None = Field(default=None, min_length=1, max_length=512)
    class_section_id: int | None = None
    session_year_id: int | None = None
    guardian_id: int | None = None
    admission_date: date | None = None
    roll_number: int | None = None


class ClassWrite(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    medium_id: int
    school_id: int | None = None
    include_semesters: int = 0


class SubjectWrite(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    medium_id: int
    school_id: int | None = None
    code: str | None = Field(default=None, max_length=64)
    type: str = "Theory"


class AttendanceWrite(BaseModel):
    class_section_id: int
    student_id: int
    session_year_id: int
    date: date
    school_id: int | None = None
    type: int = 1
    remark: str = ""


class ExamWrite(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    class_id: int
    session_year_id: int
    school_id: int | None = None
    description: str | None = None
    publish: int = 0


class FeeWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    due_date: date
    session_year_id: int
    school_id: int | None = None
    due_charges: float = 0


class AnnouncementWrite(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    session_year_id: int
    school_id: int | None = None
    description: str | None = None


class LeaveWrite(BaseModel):
    user_id: int
    reason: str = Field(min_length=1, max_length=255)
    from_date: date
    to_date: date
    session_year_id: int
    school_id: int | None = None
    status: int = 0


class ExpenseWrite(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    amount: float = 0
    date: date
    session_year_id: int
    school_id: int | None = None


class SchoolWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=2, max_length=64)
    address: str = Field(min_length=1, max_length=255)
    support_email: EmailStr
    support_phone: str = Field(min_length=6, max_length=15)
    tagline: str = Field(min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    status: int = Field(default=1, ge=0, le=1)
    admin_first_name: str = Field(min_length=1, max_length=128)
    admin_last_name: str = Field(min_length=1, max_length=128)
    admin_password: str = Field(min_length=8, max_length=128)


class SchoolPatch(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=2, max_length=64)
    address: str = Field(min_length=1, max_length=255)
    support_email: EmailStr
    support_phone: str = Field(min_length=6, max_length=15)
    tagline: str = Field(min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    status: int = Field(default=1, ge=0, le=1)


class PackageWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    status: int = 1


@router.post("/students", status_code=201)
def create_student(body: StudentWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        school_id = _school_id(body.school_id, actor_school)
        user = User(
            first_name=body.first_name.strip(),
            last_name=body.last_name.strip(),
            email=str(body.email).strip().lower(),
            password=hash_password(secrets.token_urlsafe(18)),
            status=1,
            school_id=school_id,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(user)
        db.flush()
        row = Student(
            user_id=user.id,
            class_section_id=body.class_section_id,
            admission_no=body.admission_no.strip(),
            roll_number=body.roll_number,
            admission_date=body.admission_date,
            school_id=school_id,
            guardian_id=body.guardian_id,
            session_year_id=body.session_year_id,
            created_at=_now(),
            updated_at=_now(),
        )
        db.add(row)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A record with these details already exists") from exc
        db.refresh(row)
        return {"error": False, "data": _student(row)}
    finally:
        close_admin_db(request)


@router.patch("/students/{row_id}")
def update_student(row_id: int, body: StudentPatch, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = _get_owned(db, Student, row_id, actor_school)
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(row, key, value)
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _student(row)}
    finally:
        close_admin_db(request)


@router.delete("/students/{row_id}")
def delete_student(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        _remove(db, _get_owned(db, Student, row_id, actor_school))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


def _simple_create(db, row, serializer):
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A record with these details already exists") from exc
    db.refresh(row)
    return {"error": False, "data": serializer(row)}


@router.post("/classes", status_code=201)
def create_class(body: ClassWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = SchoolClass(
            name=body.name.strip(),
            medium_id=body.medium_id,
            include_semesters=body.include_semesters,
            school_id=_school_id(body.school_id, actor_school),
            created_at=_now(),
            updated_at=_now(),
        )
        return _simple_create(db, row, _class)
    finally:
        close_admin_db(request)


@router.patch("/classes/{row_id}")
def update_class(row_id: int, body: ClassWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = _get_owned(db, SchoolClass, row_id, actor_school)
        row.name = body.name.strip()
        row.medium_id = body.medium_id
        row.include_semesters = body.include_semesters
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _class(row)}
    finally:
        close_admin_db(request)


@router.delete("/classes/{row_id}")
def delete_class(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        _remove(db, _get_owned(db, SchoolClass, row_id, actor_school))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


@router.post("/subjects", status_code=201)
def create_subject(body: SubjectWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = Subject(
            name=body.name.strip(),
            code=body.code,
            type=body.type or "Theory",
            medium_id=body.medium_id,
            school_id=_school_id(body.school_id, actor_school),
            created_at=_now(),
            updated_at=_now(),
        )
        return _simple_create(db, row, _subject)
    finally:
        close_admin_db(request)


@router.patch("/subjects/{row_id}")
def update_subject(row_id: int, body: SubjectWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = _get_owned(db, Subject, row_id, actor_school)
        row.name = body.name.strip()
        row.code = body.code
        row.type = body.type or "Theory"
        row.medium_id = body.medium_id
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _subject(row)}
    finally:
        close_admin_db(request)


@router.delete("/subjects/{row_id}")
def delete_subject(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        _remove(db, _get_owned(db, Subject, row_id, actor_school))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


@router.post("/attendances", status_code=201)
def create_attendance(body: AttendanceWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = Attendance(
            class_section_id=body.class_section_id,
            student_id=body.student_id,
            session_year_id=body.session_year_id,
            type=body.type,
            date=body.date,
            remark=body.remark or "",
            school_id=_school_id(body.school_id, actor_school),
            created_at=_now(),
            updated_at=_now(),
        )
        return _simple_create(db, row, _attendance)
    finally:
        close_admin_db(request)


@router.patch("/attendances/{row_id}")
def update_attendance(row_id: int, body: AttendanceWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = _get_owned(db, Attendance, row_id, actor_school)
        row.class_section_id = body.class_section_id
        row.student_id = body.student_id
        row.session_year_id = body.session_year_id
        row.type = body.type
        row.date = body.date
        row.remark = body.remark or ""
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _attendance(row)}
    finally:
        close_admin_db(request)


@router.delete("/attendances/{row_id}")
def delete_attendance(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        _remove(db, _get_owned(db, Attendance, row_id, actor_school))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


@router.post("/exams", status_code=201)
def create_exam(body: ExamWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = Exam(
            name=body.name.strip(),
            description=body.description,
            class_id=body.class_id,
            session_year_id=body.session_year_id,
            publish=body.publish,
            school_id=_school_id(body.school_id, actor_school),
            created_at=_now(),
            updated_at=_now(),
        )
        return _simple_create(db, row, _exam)
    finally:
        close_admin_db(request)


@router.patch("/exams/{row_id}")
def update_exam(row_id: int, body: ExamWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = _get_owned(db, Exam, row_id, actor_school)
        row.name = body.name.strip()
        row.description = body.description
        row.class_id = body.class_id
        row.session_year_id = body.session_year_id
        row.publish = body.publish
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _exam(row)}
    finally:
        close_admin_db(request)


@router.delete("/exams/{row_id}")
def delete_exam(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        _remove(db, _get_owned(db, Exam, row_id, actor_school))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


@router.post("/fees", status_code=201)
def create_fee(body: FeeWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = Fee(
            name=body.name.strip(),
            due_date=body.due_date,
            due_charges=body.due_charges,
            school_id=_school_id(body.school_id, actor_school),
            session_year_id=body.session_year_id,
            created_at=_now(),
            updated_at=_now(),
        )
        return _simple_create(db, row, _fee)
    finally:
        close_admin_db(request)


@router.patch("/fees/{row_id}")
def update_fee(row_id: int, body: FeeWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = _get_owned(db, Fee, row_id, actor_school)
        row.name = body.name.strip()
        row.due_date = body.due_date
        row.due_charges = body.due_charges
        row.session_year_id = body.session_year_id
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _fee(row)}
    finally:
        close_admin_db(request)


@router.delete("/fees/{row_id}")
def delete_fee(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        _remove(db, _get_owned(db, Fee, row_id, actor_school))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


@router.post("/announcements", status_code=201)
def create_announcement(body: AnnouncementWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = Announcement(
            title=body.title.strip(),
            description=body.description,
            session_year_id=body.session_year_id,
            school_id=_school_id(body.school_id, actor_school),
            created_at=_now(),
            updated_at=_now(),
        )
        return _simple_create(db, row, _announcement)
    finally:
        close_admin_db(request)


@router.patch("/announcements/{row_id}")
def update_announcement(row_id: int, body: AnnouncementWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = _get_owned(db, Announcement, row_id, actor_school)
        row.title = body.title.strip()
        row.description = body.description
        row.session_year_id = body.session_year_id
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _announcement(row)}
    finally:
        close_admin_db(request)


@router.delete("/announcements/{row_id}")
def delete_announcement(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        _remove(db, _get_owned(db, Announcement, row_id, actor_school))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


@router.post("/leaves", status_code=201)
def create_leave(body: LeaveWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        if body.to_date < body.from_date:
            raise HTTPException(status_code=422, detail="to_date must be on or after from_date")
        row = Leave(
            user_id=body.user_id,
            reason=body.reason.strip(),
            from_date=body.from_date,
            to_date=body.to_date,
            status=body.status,
            school_id=_school_id(body.school_id, actor_school),
            session_year_id=body.session_year_id,
            created_at=_now(),
            updated_at=_now(),
        )
        return _simple_create(db, row, _leave)
    finally:
        close_admin_db(request)


@router.patch("/leaves/{row_id}")
def update_leave(row_id: int, body: LeaveWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        if body.to_date < body.from_date:
            raise HTTPException(status_code=422, detail="to_date must be on or after from_date")
        row = _get_owned(db, Leave, row_id, actor_school)
        row.user_id = body.user_id
        row.reason = body.reason.strip()
        row.from_date = body.from_date
        row.to_date = body.to_date
        row.status = body.status
        row.session_year_id = body.session_year_id
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _leave(row)}
    finally:
        close_admin_db(request)


@router.delete("/leaves/{row_id}")
def delete_leave(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        _remove(db, _get_owned(db, Leave, row_id, actor_school))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


@router.post("/expenses", status_code=201)
def create_expense(body: ExpenseWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = Expense(
            title=body.title.strip(),
            amount=body.amount,
            date=body.date,
            school_id=_school_id(body.school_id, actor_school),
            session_year_id=body.session_year_id,
            created_at=_now(),
            updated_at=_now(),
        )
        return _simple_create(db, row, _expense)
    finally:
        close_admin_db(request)


@router.patch("/expenses/{row_id}")
def update_expense(row_id: int, body: ExpenseWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        row = _get_owned(db, Expense, row_id, actor_school)
        row.title = body.title.strip()
        row.amount = body.amount
        row.date = body.date
        row.session_year_id = body.session_year_id
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _expense(row)}
    finally:
        close_admin_db(request)


@router.delete("/expenses/{row_id}")
def delete_expense(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    try:
        _remove(db, _get_owned(db, Expense, row_id, actor_school))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


_SCHOOL_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
_SCHOOL_PHONE = re.compile(r"^[0-9]{6,15}$")


def _school_fields(body: SchoolWrite | SchoolPatch) -> tuple[str, str, str, str | None]:
    code = body.code.strip()
    if not _SCHOOL_CODE.match(code):
        raise HTTPException(
            status_code=422,
            detail="School code must be 2–64 letters, numbers, hyphens, or underscores.",
        )
    phone = body.support_phone.strip()
    if not _SCHOOL_PHONE.match(phone):
        raise HTTPException(status_code=422, detail="Support phone must be 6 to 15 digits.")
    email = str(body.support_email).strip().lower()
    domain = (body.domain or "").strip() or None
    return code, phone, email, domain


def _reject_school_duplicate(db, *, code: str, email: str, domain: str | None, exclude_id: int | None) -> None:
    def taken(column, value: str) -> bool:
        query = select(School.id).where(func.lower(column) == value.lower())
        if exclude_id is not None:
            query = query.where(School.id != exclude_id)
        return db.scalar(query) is not None

    if taken(School.code, code):
        raise HTTPException(status_code=409, detail="A school with this code already exists.")
    if taken(School.support_email, email):
        raise HTTPException(status_code=409, detail="A school with this support email already exists.")
    if domain and taken(School.domain, domain):
        raise HTTPException(status_code=409, detail="A school with this domain already exists.")


@router.post("/schools", status_code=201)
def create_school(body: SchoolWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    if actor_school is not None:
        raise HTTPException(status_code=403, detail="Only a platform admin can create schools")
    try:
        code, phone, email, domain = _school_fields(body)
        _reject_school_duplicate(db, code=code, email=email, domain=domain, exclude_id=None)
        now = _now()
        row = School(
            name=body.name.strip(),
            code=code,
            address=body.address.strip(),
            support_email=email,
            support_phone=phone,
            tagline=body.tagline.strip(),
            domain=domain,
            logo="",
            status=body.status,
            installed=1,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        db.flush()
        row.database_name = f"school_{row.id}"
        admin = User(
            first_name=body.admin_first_name.strip(),
            last_name=body.admin_last_name.strip(),
            email=email,
            mobile=phone,
            password=hash_password(body.admin_password),
            status=1,
            school_id=row.id,
            created_at=now,
            updated_at=now,
        )
        db.add(admin)
        db.flush()
        row.admin_id = admin.id
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A school with these details already exists.") from exc
        db.refresh(row)
        data = _school(row)
        data["admin"] = {
            "id": admin.id,
            "first_name": admin.first_name,
            "last_name": admin.last_name,
            "email": admin.email,
            "mobile": admin.mobile,
        }
        return {"error": False, "message": "School created", "data": data}
    finally:
        close_admin_db(request)


@router.patch("/schools/{row_id}")
def update_school(row_id: int, body: SchoolPatch, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    if actor_school is not None:
        raise HTTPException(status_code=403, detail="Only a platform admin can update schools")
    try:
        row = _get_owned(db, School, row_id, None)
        code, phone, email, domain = _school_fields(body)
        _reject_school_duplicate(db, code=code, email=email, domain=domain, exclude_id=row.id)
        row.name = body.name.strip()
        row.code = code
        row.address = body.address.strip()
        row.support_email = email
        row.support_phone = phone
        row.tagline = body.tagline.strip()
        row.domain = domain
        row.status = body.status
        if row.admin_id:
            admin = db.get(User, row.admin_id)
            if admin is not None and admin.deleted_at is None:
                admin.email = email
                admin.mobile = phone
                admin.updated_at = _now()
        _touch(row)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="A school with these details already exists.") from exc
        db.refresh(row)
        return {"error": False, "message": "School updated", "data": _school(row)}
    finally:
        close_admin_db(request)


@router.delete("/schools/{row_id}")
def delete_school(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    if actor_school is not None:
        raise HTTPException(status_code=403, detail="Only a platform admin can delete schools")
    try:
        _remove(db, _get_owned(db, School, row_id, None))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)


@router.post("/packages", status_code=201)
def create_package(body: PackageWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    if actor_school is not None:
        raise HTTPException(status_code=403, detail="Only a platform admin can create packages")
    try:
        row = Package(
            name=body.name.strip(),
            description=body.description,
            status=body.status,
            created_at=_now(),
            updated_at=_now(),
        )
        return _simple_create(db, row, _package)
    finally:
        close_admin_db(request)


@router.patch("/packages/{row_id}")
def update_package(row_id: int, body: PackageWrite, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    if actor_school is not None:
        raise HTTPException(status_code=403, detail="Only a platform admin can update packages")
    try:
        row = _get_owned(db, Package, row_id, None)
        row.name = body.name.strip()
        row.description = body.description
        row.status = body.status
        _touch(row)
        db.commit()
        db.refresh(row)
        return {"error": False, "data": _package(row)}
    finally:
        close_admin_db(request)


@router.delete("/packages/{row_id}")
def delete_package(row_id: int, request: Request, context=Depends(_guard)):
    db, _user, actor_school = context
    if actor_school is not None:
        raise HTTPException(status_code=403, detail="Only a platform admin can delete packages")
    try:
        _remove(db, _get_owned(db, Package, row_id, None))
        return {"error": False, "message": "Deleted"}
    finally:
        close_admin_db(request)
