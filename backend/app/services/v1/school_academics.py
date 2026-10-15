"""School-admin academic records. school_id always comes from the authenticated user."""

from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
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
    Staff,
    Student,
    Subject,
    User,
)

PAGE_SIZE_MAX = 50


class AcademicError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _page(page: int, page_size: int) -> tuple[int, int]:
    safe_page = page if page >= 1 else 1
    safe_size = page_size if 1 <= page_size <= PAGE_SIZE_MAX else 20
    return safe_page, safe_size


def _envelope(items: list[dict], total: int, page: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _user_name(user: User | None) -> str:
    if user is None:
        return ""
    return f"{user.first_name} {user.last_name}".strip()


def _owned(db: Session, model, row_id: int, school_id: int):
    row = db.get(model, row_id)
    if row is None or getattr(row, "school_id", None) != school_id:
        raise AcademicError(404, "Record not found")
    deleted = getattr(row, "deleted_at", None)
    if deleted is not None:
        raise AcademicError(404, "Record not found")
    return row


def _same_school(db: Session, model, row_id: int, school_id: int, label: str):
    row = db.get(model, row_id)
    if row is None or getattr(row, "school_id", None) != school_id or getattr(row, "deleted_at", None):
        raise AcademicError(422, f"{label} does not belong to this school")
    return row


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AcademicError(409, "A record with these details already exists") from exc


def summary(db: Session, school_id: int, session_year_id: int | None = None) -> dict:
    def active(model, session_field: str | None = None) -> int:
        query = db.query(func.count(model.id)).filter(model.school_id == school_id)
        if hasattr(model, "deleted_at"):
            query = query.filter(model.deleted_at.is_(None))
        if session_year_id and session_field and hasattr(model, session_field):
            query = query.filter(getattr(model, session_field) == session_year_id)
        return int(query.scalar() or 0)

    guardians = (
        db.query(func.count(func.distinct(Student.guardian_id)))
        .filter(Student.school_id == school_id, Student.deleted_at.is_(None))
        .scalar()
        or 0
    )
    today = date.today()
    attendance = db.query(Attendance).filter(Attendance.school_id == school_id, Attendance.date == today)
    if session_year_id:
        attendance = attendance.filter(Attendance.session_year_id == session_year_id)
    present = attendance.filter(Attendance.type == 1).count()
    absent = attendance.filter(Attendance.type != 1).count()
    leaves = db.query(Leave).filter(Leave.school_id == school_id, Leave.from_date <= today, Leave.to_date >= today)
    if session_year_id:
        leaves = leaves.filter(Leave.session_year_id == session_year_id)
    leave_rows = leaves.order_by(Leave.id.desc()).limit(8).all()
    return {
        "students": active(Student, "session_year_id"),
        "teachers": active(Staff),
        "guardians": int(guardians),
        "classes": active(SchoolClass),
        "sections": active(Section),
        "subjects": active(Subject),
        "exams": active(Exam, "session_year_id"),
        "fees": active(Fee, "session_year_id"),
        "announcements": active(Announcement, "session_year_id"),
        "attendance_today": {"present": int(present), "absent": int(absent)},
        "leaves_today": {
            "count": leaves.count(),
            "items": [
                {"id": row.id, "reason": row.reason, "user_id": row.user_id, "status": row.status}
                for row in leave_rows
            ],
        },
        "finance_months": _finance_months(db, school_id, session_year_id),
    }


def _finance_months(db: Session, school_id: int, session_year_id: int | None) -> list[dict]:
    """Recorded expenses and fee charges by month. Fee charges are amounts due, not collected income."""
    expenses = db.query(Expense).filter(Expense.school_id == school_id)
    fees = db.query(Fee).filter(Fee.school_id == school_id, Fee.deleted_at.is_(None))
    if session_year_id:
        expenses = expenses.filter(Expense.session_year_id == session_year_id)
        fees = fees.filter(Fee.session_year_id == session_year_id)
    expense_rows = expenses.all()
    fee_rows = fees.all()
    months: dict[str, dict] = {}
    for row in expense_rows:
        key = row.date.strftime("%Y-%m")
        bucket = months.setdefault(key, {"month": row.date.strftime("%b"), "expenses": 0.0, "fee_charges": 0.0})
        bucket["expenses"] += float(row.amount or 0)
    for row in fee_rows:
        key = row.due_date.strftime("%Y-%m")
        bucket = months.setdefault(key, {"month": row.due_date.strftime("%b"), "expenses": 0.0, "fee_charges": 0.0})
        bucket["fee_charges"] += float(row.due_charges or 0)
    return [months[key] for key in sorted(months)]


def create_expense(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
    row = Expense(
        title=body["title"].strip(),
        amount=float(body.get("amount") or 0),
        date=body["date"],
        session_year_id=int(body["session_year_id"]),
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "name": row.title, "title": row.title, "amount": row.amount, "date": row.date.isoformat(), "session_year_id": row.session_year_id}
    def active(model) -> int:
        query = db.query(func.count(model.id)).filter(model.school_id == school_id)
        if hasattr(model, "deleted_at"):
            query = query.filter(model.deleted_at.is_(None))
        return int(query.scalar() or 0)

    guardians = (
        db.query(func.count(func.distinct(Student.guardian_id)))
        .filter(Student.school_id == school_id, Student.deleted_at.is_(None))
        .scalar()
        or 0
    )
    today = date.today()
    present = (
        db.query(func.count(Attendance.id))
        .filter(Attendance.school_id == school_id, Attendance.date == today, Attendance.type == 1)
        .scalar()
        or 0
    )
    absent = (
        db.query(func.count(Attendance.id))
        .filter(Attendance.school_id == school_id, Attendance.date == today, Attendance.type != 1)
        .scalar()
        or 0
    )
    return {
        "students": active(Student),
        "teachers": active(Staff),
        "guardians": int(guardians),
        "classes": active(SchoolClass),
        "sections": active(Section),
        "subjects": active(Subject),
        "exams": active(Exam),
        "fees": active(Fee),
        "announcements": active(Announcement),
        "attendance_today": {"present": int(present), "absent": int(absent)},
    }


def _student_item(row: Student, user: User | None, guardian: User | None) -> dict:
    return {
        "id": row.id,
        "first_name": user.first_name if user else "",
        "last_name": user.last_name if user else "",
        "email": user.email if user else "",
        "admission_no": row.admission_no,
        "roll_number": row.roll_number,
        "class_section_id": row.class_section_id,
        "session_year_id": row.session_year_id,
        "guardian_id": row.guardian_id,
        "guardian_name": _user_name(guardian),
        "admission_date": row.admission_date.isoformat() if row.admission_date else None,
        "status": user.status if user else 0,
    }


def list_students(db: Session, school_id: int, q: str, page: int, page_size: int) -> dict:
    page, page_size = _page(page, page_size)
    guardian = db.query(User).filter(User.id == Student.guardian_id).subquery()
    query = (
        db.query(Student, User)
        .join(User, Student.user_id == User.id)
        .filter(Student.school_id == school_id, Student.deleted_at.is_(None))
    )
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(User.first_name.ilike(like), User.last_name.ilike(like), User.email.ilike(like), Student.admission_no.ilike(like))
        )
    total = query.count()
    rows = query.order_by(Student.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for row, user in rows:
        parent = db.get(User, row.guardian_id)
        items.append(_student_item(row, user, parent))
    del guardian
    return _envelope(items, total, page, page_size)


def create_student(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, ClassSection, int(body["class_section_id"]), school_id, "Class section")
    _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
    guardian = _same_school(db, User, int(body["guardian_id"]), school_id, "Guardian")
    user = User(
        first_name=body["first_name"].strip(),
        last_name=body["last_name"].strip(),
        email=body["email"].strip().lower(),
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
        class_section_id=int(body["class_section_id"]),
        admission_no=body["admission_no"].strip(),
        roll_number=body.get("roll_number"),
        admission_date=body["admission_date"],
        school_id=school_id,
        guardian_id=guardian.id,
        session_year_id=int(body["session_year_id"]),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _student_item(row, user, guardian)


def update_student(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, Student, row_id, school_id)
    if "class_section_id" in body:
        _same_school(db, ClassSection, int(body["class_section_id"]), school_id, "Class section")
        row.class_section_id = int(body["class_section_id"])
    if "session_year_id" in body:
        _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
        row.session_year_id = int(body["session_year_id"])
    if "guardian_id" in body:
        _same_school(db, User, int(body["guardian_id"]), school_id, "Guardian")
        row.guardian_id = int(body["guardian_id"])
    if "admission_no" in body:
        row.admission_no = body["admission_no"].strip()
    if "roll_number" in body:
        row.roll_number = body["roll_number"]
    if "admission_date" in body:
        row.admission_date = body["admission_date"]
    row.updated_at = _now()
    user = db.get(User, row.user_id)
    if user is not None:
        if "first_name" in body:
            user.first_name = body["first_name"].strip()
        if "last_name" in body:
            user.last_name = body["last_name"].strip()
        if "status" in body:
            user.status = int(body["status"])
        user.updated_at = _now()
    _commit(db)
    return _student_item(row, user, db.get(User, row.guardian_id))


def delete_student(db: Session, school_id: int, row_id: int) -> None:
    row = _owned(db, Student, row_id, school_id)
    row.deleted_at = _now()
    row.updated_at = _now()
    user = db.get(User, row.user_id)
    if user is not None:
        user.status = 0
        user.deleted_at = _now()
    _commit(db)


def _named(row, extra: dict | None = None) -> dict:
    data = {"id": row.id, "name": getattr(row, "name", "")}
    if extra:
        data.update(extra)
    return data


def list_named(db: Session, model, school_id: int, q: str, page: int, page_size: int, extra) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(model).filter(model.school_id == school_id)
    if hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at.is_(None))
    if q.strip() and hasattr(model, "name"):
        query = query.filter(model.name.ilike(f"%{q.strip()}%"))
    total = query.count()
    rows = query.order_by(model.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([extra(row) for row in rows], total, page, page_size)


def create_medium(db: Session, school_id: int, name: str) -> dict:
    row = Medium(name=name.strip(), school_id=school_id, created_at=_now(), updated_at=_now())
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _named(row)


def create_session(db: Session, school_id: int, body: dict) -> dict:
    row = SessionYear(
        name=body["name"].strip(),
        start_date=body["start_date"],
        end_date=body["end_date"],
        default=int(body.get("default") or 0),
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    if row.end_date < row.start_date:
        raise AcademicError(422, "End date must be on or after the start date")
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "name": row.name, "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(), "default": row.default}


def create_section(db: Session, school_id: int, name: str) -> dict:
    row = Section(name=name.strip(), school_id=school_id, created_at=_now(), updated_at=_now())
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _named(row)


def create_class(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, Medium, int(body["medium_id"]), school_id, "Medium")
    row = SchoolClass(
        name=body["name"].strip(),
        medium_id=int(body["medium_id"]),
        include_semesters=int(body.get("include_semesters") or 0),
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "name": row.name, "medium_id": row.medium_id, "include_semesters": row.include_semesters}


def create_class_section(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, SchoolClass, int(body["class_id"]), school_id, "Class")
    _same_school(db, Section, int(body["section_id"]), school_id, "Section")
    _same_school(db, Medium, int(body["medium_id"]), school_id, "Medium")
    row = ClassSection(
        class_id=int(body["class_id"]),
        section_id=int(body["section_id"]),
        medium_id=int(body["medium_id"]),
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "class_id": row.class_id, "section_id": row.section_id, "medium_id": row.medium_id, "name": f"{row.class_id}-{row.section_id}"}


def create_subject(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, Medium, int(body["medium_id"]), school_id, "Medium")
    row = Subject(
        name=body["name"].strip(),
        code=(body.get("code") or "").strip() or None,
        type=(body.get("type") or "Theory").strip(),
        medium_id=int(body["medium_id"]),
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "name": row.name, "code": row.code, "type": row.type, "medium_id": row.medium_id}


def create_attendance(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, ClassSection, int(body["class_section_id"]), school_id, "Class section")
    _same_school(db, Student, int(body["student_id"]), school_id, "Student")
    _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
    kind = int(body.get("type") or 1)
    if kind not in (0, 1, 2):
        raise AcademicError(422, "Attendance type must be 1 present, 0 absent, or 2 late")
    row = Attendance(
        class_section_id=int(body["class_section_id"]),
        student_id=int(body["student_id"]),
        session_year_id=int(body["session_year_id"]),
        type=kind,
        date=body["date"],
        remark=(body.get("remark") or "")[:512],
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "student_id": row.student_id, "class_section_id": row.class_section_id, "session_year_id": row.session_year_id, "type": row.type, "date": row.date.isoformat(), "remark": row.remark, "name": row.date.isoformat()}


def create_exam(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, SchoolClass, int(body["class_id"]), school_id, "Class")
    _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
    row = Exam(
        name=body["name"].strip(),
        description=body.get("description"),
        class_id=int(body["class_id"]),
        session_year_id=int(body["session_year_id"]),
        publish=1 if int(body.get("publish") or 0) else 0,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "name": row.name, "class_id": row.class_id, "session_year_id": row.session_year_id, "publish": row.publish, "description": row.description}


def create_fee(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
    row = Fee(
        name=body["name"].strip(),
        due_date=body["due_date"],
        due_charges=float(body.get("due_charges") or 0),
        session_year_id=int(body["session_year_id"]),
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "name": row.name, "due_date": row.due_date.isoformat(), "due_charges": row.due_charges, "session_year_id": row.session_year_id}


def create_announcement(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
    row = Announcement(
        title=body["title"].strip(),
        description=body.get("description"),
        session_year_id=int(body["session_year_id"]),
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "name": row.title, "title": row.title, "description": row.description, "session_year_id": row.session_year_id}


def create_leave(db: Session, school_id: int, body: dict) -> dict:
    user = _same_school(db, User, int(body["user_id"]), school_id, "User")
    _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
    if body["to_date"] < body["from_date"]:
        raise AcademicError(422, "Leave end date must be on or after the start date")
    row = Leave(
        user_id=user.id,
        reason=body["reason"].strip(),
        from_date=body["from_date"],
        to_date=body["to_date"],
        status=int(body.get("status") or 0),
        session_year_id=int(body["session_year_id"]),
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {"id": row.id, "name": row.reason, "user_id": row.user_id, "reason": row.reason, "from_date": row.from_date.isoformat(), "to_date": row.to_date.isoformat(), "status": row.status, "session_year_id": row.session_year_id}


def list_people(db: Session, school_id: int, kind: str, q: str, page: int, page_size: int) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(User).filter(User.school_id == school_id, User.deleted_at.is_(None))
    student_ids = {row[0] for row in db.query(Student.user_id).filter(Student.school_id == school_id, Student.deleted_at.is_(None)).all()}
    staff_ids = {row[0] for row in db.query(Staff.user_id).filter(Staff.school_id == school_id).all()}
    if kind == "teachers":
        query = query.filter(User.id.in_(staff_ids or {-1}))
    elif kind == "parents":
        if student_ids:
            query = query.filter(User.id.notin_(student_ids))
        if staff_ids:
            query = query.filter(User.id.notin_(staff_ids))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(User.first_name.ilike(like), User.last_name.ilike(like), User.email.ilike(like)))
    total = query.count()
    rows = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [{"id": row.id, "name": _user_name(row), "first_name": row.first_name, "last_name": row.last_name, "email": row.email, "mobile": row.mobile, "status": row.status} for row in rows]
    return _envelope(items, total, page, page_size)


def create_person(db: Session, school_id: int, kind: str, body: dict) -> dict:
    user = User(
        first_name=body["first_name"].strip(),
        last_name=body["last_name"].strip(),
        email=body["email"].strip().lower(),
        mobile=(body.get("mobile") or "").strip() or None,
        password=hash_password(secrets.token_urlsafe(18)),
        status=1,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(user)
    db.flush()
    if kind == "teachers":
        db.add(Staff(user_id=user.id, school_id=school_id, qualification=(body.get("qualification") or "").strip() or None, salary=float(body.get("salary") or 0), created_at=_now(), updated_at=_now()))
    _commit(db)
    db.refresh(user)
    return {"id": user.id, "name": _user_name(user), "first_name": user.first_name, "last_name": user.last_name, "email": user.email, "mobile": user.mobile, "status": user.status}


def soft_delete(db: Session, model, school_id: int, row_id: int) -> None:
    row = _owned(db, model, row_id, school_id)
    if hasattr(row, "deleted_at"):
        row.deleted_at = _now()
        if hasattr(row, "updated_at"):
            row.updated_at = _now()
    else:
        db.delete(row)
    _commit(db)
