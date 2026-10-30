"""School-admin academic records. school_id always comes from the authenticated user."""

from __future__ import annotations

import secrets
from datetime import date, datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tables import (
    USER_MODEL,
    Announcement,
    Attendance,
    ClassSection,
    ClassSubject,
    Exam,
    Expense,
    Fee,
    Leave,
    LeaveType,
    Medium,
    ModelHasRole,
    Role,
    SchoolClass,
    Section,
    SessionYear,
    Staff,
    Student,
    Subject,
    TeacherAssignment,
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


# Client must never set ownership or internal identity fields.
_WRITE_BLOCKLIST = frozenset(
    {
        "school_id",
        "id",
        "deleted_at",
        "created_at",
        "updated_at",
        "staff_id",
        "teacher_user_id",
    }
)


def sanitize_write_body(body: dict) -> dict:
    """Drop ownership / internal fields even if a client smuggles them past the schema."""
    return {key: value for key, value in body.items() if key not in _WRITE_BLOCKLIST}


# Foreign keys a generic PATCH may set, with the model that must belong to the school.
_REFERENCES = {
    "class_id": (SchoolClass, "Class"),
    "section_id": (Section, "Section"),
    "session_year_id": (SessionYear, "Session year"),
    "session_id": (SessionYear, "Session year"),
    "medium_id": (Medium, "Medium"),
    "class_section_id": (ClassSection, "Class section"),
    "student_id": (Student, "Student"),
    "user_id": (User, "User"),
    "guardian_id": (User, "Guardian"),
}
REFERENCE_FIELDS = tuple(_REFERENCES)


def check_references(db: Session, school_id: int, row, data: dict) -> None:
    """Reject updates that point a row at another school's records (422)."""
    for key, (model, label) in _REFERENCES.items():
        value = data.get(key)
        if value is None:
            continue
        # session_id is an API alias for session_year_id (row may only have the latter).
        if key == "session_id":
            _same_school(db, model, int(value), school_id, label)
            continue
        if hasattr(row, key):
            _same_school(db, model, int(value), school_id, label)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Never surface SQL / constraint text to clients.
        raise AcademicError(409, "A record with these details already exists")


def _ensure_school_role(db: Session, school_id: int, role_name: str) -> Role:
    """Get or create a school-scoped Spatie role (web guard)."""
    role = db.scalar(
        select(Role).where(
            Role.name == role_name,
            Role.guard_name == "web",
            Role.school_id == school_id,
        )
    )
    if role is not None:
        return role
    role = Role(
        name=role_name,
        guard_name="web",
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(role)
    db.flush()
    return role


def _assign_user_role(db: Session, user_id: int, role: Role) -> None:
    existing = db.scalar(
        select(ModelHasRole).where(
            ModelHasRole.role_id == role.id,
            ModelHasRole.model_id == user_id,
            ModelHasRole.model_type == USER_MODEL,
        )
    )
    if existing is not None:
        return
    db.add(ModelHasRole(role_id=role.id, model_id=user_id, model_type=USER_MODEL))


def _assert_unique_school_email(db: Session, school_id: int, email: str) -> None:
    existing = (
        db.query(User)
        .filter(
            User.school_id == school_id,
            func.lower(User.email) == email.lower(),
            User.deleted_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        raise AcademicError(409, "A user with this email already exists in this school")


def summary(db: Session, school_id: int, session_year_id: int | None = None) -> dict:
    if session_year_id is not None:
        _owned(db, SessionYear, session_year_id, school_id)
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


def list_named(
    db: Session,
    model,
    school_id: int,
    q: str,
    page: int,
    page_size: int,
    extra,
    *,
    filters: dict | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(model).filter(model.school_id == school_id)
    if hasattr(model, "deleted_at"):
        query = query.filter(model.deleted_at.is_(None))
    if q.strip() and hasattr(model, "name"):
        query = query.filter(model.name.ilike(f"%{q.strip()}%"))
    for key, value in (filters or {}).items():
        if value is None or not hasattr(model, key):
            continue
        query = query.filter(getattr(model, key) == value)
    total = query.count()
    rows = query.order_by(model.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([extra(row) for row in rows], total, page, page_size)


def list_sessions(db: Session, school_id: int, q: str, page: int, page_size: int) -> dict:
    return list_named(
        db,
        SessionYear,
        school_id,
        q,
        page,
        page_size,
        lambda row: {
            "id": row.id,
            "name": row.name,
            "default": row.default,
            "start_date": row.start_date.isoformat(),
            "end_date": row.end_date.isoformat(),
        },
    )


def list_classes(
    db: Session, school_id: int, q: str, page: int, page_size: int, *, medium_id: int | None = None
) -> dict:
    if medium_id is not None:
        _owned(db, Medium, medium_id, school_id)
    return list_named(
        db,
        SchoolClass,
        school_id,
        q,
        page,
        page_size,
        _class_item,
        filters={"medium_id": medium_id},
    )


def _section_item(row: Section) -> dict:
    return {"id": row.id, "name": row.name}


def list_sections(
    db: Session,
    school_id: int,
    q: str,
    page: int,
    page_size: int,
    *,
    class_id: int | None = None,
) -> dict:
    """List school sections. With class_id, only sections linked via class_sections."""
    if class_id is None:
        return list_named(
            db, Section, school_id, q, page, page_size, _section_item
        )
    klass = _owned(db, SchoolClass, class_id, school_id)
    page, page_size = _page(page, page_size)
    query = (
        db.query(Section, ClassSection)
        .join(
            ClassSection,
            ClassSection.section_id == Section.id,
        )
        .filter(
            Section.school_id == school_id,
            Section.deleted_at.is_(None),
            ClassSection.school_id == school_id,
            ClassSection.class_id == class_id,
            ClassSection.deleted_at.is_(None),
        )
    )
    if q.strip():
        query = query.filter(Section.name.ilike(f"%{q.strip()}%"))
    total = query.count()
    rows = (
        query.order_by(Section.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            **_section_item(section),
            "class_id": klass.id,
            "class_name": klass.name,
            "medium_id": link.medium_id,
            "class_section_id": link.id,
        }
        for section, link in rows
    ]
    return _envelope(items, total, page, page_size)


def _subject_item(row: Subject) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "code": row.code,
        "type": row.type,
        "medium_id": row.medium_id,
    }


# Legacy eSchool subject.type values. Compulsory/Elective are not in the schema.
SUBJECT_TYPES = frozenset({"Theory", "Practical"})


def list_subjects(
    db: Session,
    school_id: int,
    q: str,
    page: int,
    page_size: int,
    *,
    medium_id: int | None = None,
    class_id: int | None = None,
) -> dict:
    """List school subjects. Optional class_id filters via class_subjects."""
    if medium_id is not None:
        _owned(db, Medium, medium_id, school_id)
    if class_id is not None:
        _owned(db, SchoolClass, class_id, school_id)
        page, page_size = _page(page, page_size)
        query = (
            db.query(Subject)
            .join(ClassSubject, ClassSubject.subject_id == Subject.id)
            .filter(
                Subject.school_id == school_id,
                Subject.deleted_at.is_(None),
                ClassSubject.school_id == school_id,
                ClassSubject.class_id == class_id,
                ClassSubject.deleted_at.is_(None),
            )
        )
        if medium_id is not None:
            query = query.filter(Subject.medium_id == medium_id)
        if q.strip():
            term = f"%{q.strip()}%"
            query = query.filter(or_(Subject.name.ilike(term), Subject.code.ilike(term)))
        total = query.count()
        rows = (
            query.order_by(Subject.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return _envelope([_subject_item(row) for row in rows], total, page, page_size)

    page, page_size = _page(page, page_size)
    query = db.query(Subject).filter(Subject.school_id == school_id, Subject.deleted_at.is_(None))
    if medium_id is not None:
        query = query.filter(Subject.medium_id == medium_id)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(Subject.name.ilike(term), Subject.code.ilike(term)))
    total = query.count()
    rows = query.order_by(Subject.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_subject_item(row) for row in rows], total, page, page_size)


def list_class_sections(
    db: Session,
    school_id: int,
    page: int,
    page_size: int,
    *,
    class_id: int | None = None,
    medium_id: int | None = None,
) -> dict:
    if class_id is not None:
        _owned(db, SchoolClass, class_id, school_id)
    if medium_id is not None:
        _owned(db, Medium, medium_id, school_id)
    page, page_size = _page(page, page_size)
    query = db.query(ClassSection).filter(
        ClassSection.school_id == school_id, ClassSection.deleted_at.is_(None)
    )
    if class_id is not None:
        query = query.filter(ClassSection.class_id == class_id)
    if medium_id is not None:
        query = query.filter(ClassSection.medium_id == medium_id)
    total = query.count()
    rows = query.order_by(ClassSection.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    class_ids = {row.class_id for row in rows}
    section_ids = {row.section_id for row in rows}
    classes = {
        row.id: row.name
        for row in db.query(SchoolClass).filter(SchoolClass.id.in_(class_ids or {-1})).all()
    }
    sections = {
        row.id: row.name for row in db.query(Section).filter(Section.id.in_(section_ids or {-1})).all()
    }
    items = [
        {
            "id": row.id,
            "name": f"{classes.get(row.class_id, row.class_id)} / {sections.get(row.section_id, row.section_id)}",
            "class_id": row.class_id,
            "section_id": row.section_id,
            "medium_id": row.medium_id,
            "class_name": classes.get(row.class_id),
            "section_name": sections.get(row.section_id),
        }
        for row in rows
    ]
    return _envelope(items, total, page, page_size)


def create_medium(db: Session, school_id: int, name: str) -> dict:
    row = Medium(name=name.strip(), school_id=school_id, created_at=_now(), updated_at=_now())
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _named(row)


def _session_item(row: SessionYear) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "default": row.default,
        "start_date": row.start_date.isoformat(),
        "end_date": row.end_date.isoformat(),
    }


def _normalize_session_name(name: str | None) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise AcademicError(422, "Session name is required")
    if len(cleaned) > 512:
        raise AcademicError(422, "Session name must be at most 512 characters")
    return cleaned


def _assert_unique_session_name(
    db: Session, school_id: int, name: str, *, exclude_id: int | None = None
) -> None:
    query = db.query(SessionYear).filter(
        SessionYear.school_id == school_id,
        SessionYear.deleted_at.is_(None),
        func.lower(SessionYear.name) == name.lower(),
    )
    if exclude_id is not None:
        query = query.filter(SessionYear.id != exclude_id)
    if query.first() is not None:
        raise AcademicError(409, "A session with this name already exists")


def _validate_session_dates(start_date: date, end_date: date) -> None:
    if end_date < start_date:
        raise AcademicError(422, "End date must be on or after the start date")


def _lock_school_sessions(db: Session, school_id: int) -> list[SessionYear]:
    """Serialize activate/create-default for one school (FOR UPDATE)."""
    return list(
        db.scalars(
            select(SessionYear)
            .where(SessionYear.school_id == school_id, SessionYear.deleted_at.is_(None))
            .order_by(SessionYear.id.asc())
            .with_for_update()
        )
    )


def get_session(db: Session, school_id: int, session_id: int) -> dict:
    return _session_item(_owned(db, SessionYear, session_id, school_id))


def activate_session(db: Session, school_id: int, session_id: int) -> dict:
    """Set one session as default and clear default on every other session for the school."""
    rows = _lock_school_sessions(db, school_id)
    row = next((item for item in rows if item.id == session_id), None)
    if row is None:
        raise AcademicError(404, "Record not found")
    now = _now()
    for item in rows:
        item.default = 1 if item.id == session_id else 0
        item.updated_at = now
    _commit(db)
    db.refresh(row)
    return _session_item(row)


def create_session(db: Session, school_id: int, body: dict) -> dict:
    if "name" not in body or "start_date" not in body or "end_date" not in body:
        raise AcademicError(422, "name, start_date, and end_date are required")
    name = _normalize_session_name(body["name"])
    start_date = body["start_date"]
    end_date = body["end_date"]
    _validate_session_dates(start_date, end_date)
    make_default = int(body.get("default") or 0) == 1
    if make_default:
        _lock_school_sessions(db, school_id)
    _assert_unique_session_name(db, school_id, name)
    row = SessionYear(
        name=name,
        start_date=start_date,
        end_date=end_date,
        default=1 if make_default else 0,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    if make_default:
        db.query(SessionYear).filter(
            SessionYear.school_id == school_id,
            SessionYear.deleted_at.is_(None),
            SessionYear.id != row.id,
            SessionYear.default != 0,
        ).update({"default": 0, "updated_at": _now()}, synchronize_session=False)
    _commit(db)
    db.refresh(row)
    return _session_item(row)


def update_session(db: Session, school_id: int, session_id: int, body: dict) -> dict:
    raw = dict(body)
    activate = raw.pop("default", None) == 1
    clear_default = "default" in body and int(body.get("default") or 0) == 0
    if activate or clear_default:
        rows = _lock_school_sessions(db, school_id)
        row = next((item for item in rows if item.id == session_id), None)
        if row is None:
            raise AcademicError(404, "Record not found")
    else:
        row = _owned(db, SessionYear, session_id, school_id)
    if "name" in raw:
        name = _normalize_session_name(raw["name"])
        _assert_unique_session_name(db, school_id, name, exclude_id=row.id)
        row.name = name
    if "start_date" in raw:
        row.start_date = raw["start_date"]
    if "end_date" in raw:
        row.end_date = raw["end_date"]
    _validate_session_dates(row.start_date, row.end_date)
    row.updated_at = _now()
    if activate:
        _commit(db)
        return activate_session(db, school_id, session_id)
    if clear_default:
        row.default = 0
    _commit(db)
    db.refresh(row)
    return _session_item(row)


def soft_delete_session(db: Session, school_id: int, session_id: int) -> None:
    row = _owned(db, SessionYear, session_id, school_id)
    row.deleted_at = _now()
    row.default = 0
    row.updated_at = _now()
    _commit(db)


def _normalize_section_name(name: str | None) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise AcademicError(422, "Section name is required")
    if len(cleaned) > 512:
        raise AcademicError(422, "Section name must be at most 512 characters")
    return cleaned


def _find_section_by_name(db: Session, school_id: int, name: str) -> Section | None:
    return (
        db.query(Section)
        .filter(
            Section.school_id == school_id,
            Section.deleted_at.is_(None),
            func.lower(Section.name) == name.lower(),
        )
        .order_by(Section.id.asc())
        .first()
    )


def _assert_unique_section_name_in_class(
    db: Session,
    school_id: int,
    class_id: int,
    name: str,
    *,
    exclude_section_id: int | None = None,
) -> None:
    """No other active section with this name may already be linked to the class."""
    query = (
        db.query(Section)
        .join(ClassSection, ClassSection.section_id == Section.id)
        .filter(
            Section.school_id == school_id,
            Section.deleted_at.is_(None),
            ClassSection.school_id == school_id,
            ClassSection.class_id == class_id,
            ClassSection.deleted_at.is_(None),
            func.lower(Section.name) == name.lower(),
        )
    )
    if exclude_section_id is not None:
        query = query.filter(Section.id != exclude_section_id)
    if query.first() is not None:
        raise AcademicError(409, "A section with this name already exists for the class")


def _section_class_links(db: Session, school_id: int, section_id: int) -> list[ClassSection]:
    return (
        db.query(ClassSection)
        .filter(
            ClassSection.school_id == school_id,
            ClassSection.section_id == section_id,
            ClassSection.deleted_at.is_(None),
        )
        .order_by(ClassSection.id.asc())
        .all()
    )


def _section_detail(db: Session, school_id: int, row: Section) -> dict:
    links = _section_class_links(db, school_id, row.id)
    class_ids = {link.class_id for link in links}
    classes_by_id = {
        klass.id: klass
        for klass in db.query(SchoolClass).filter(SchoolClass.id.in_(class_ids or {-1})).all()
    }
    item = _section_item(row)
    item["classes"] = [
        {
            "class_id": link.class_id,
            "class_name": classes_by_id[link.class_id].name if link.class_id in classes_by_id else None,
            "medium_id": link.medium_id,
            "class_section_id": link.id,
        }
        for link in links
    ]
    return item


def get_section(db: Session, school_id: int, section_id: int) -> dict:
    row = _owned(db, Section, section_id, school_id)
    return _section_detail(db, school_id, row)


def create_section(db: Session, school_id: int, name: str) -> dict:
    """School-level section only (academics compat). No class mapping."""
    cleaned = _normalize_section_name(name)
    row = Section(name=cleaned, school_id=school_id, created_at=_now(), updated_at=_now())
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _section_item(row)


def create_section_for_class(db: Session, school_id: int, body: dict) -> dict:
    """Create or reuse a school section and link it to a class via class_sections."""
    if "name" not in body or "class_id" not in body:
        raise AcademicError(422, "name and class_id are required")
    name = _normalize_section_name(body["name"])
    class_id = int(body["class_id"])
    klass = _owned(db, SchoolClass, class_id, school_id)
    _assert_unique_section_name_in_class(db, school_id, class_id, name)

    section = _find_section_by_name(db, school_id, name)
    if section is None:
        section = Section(name=name, school_id=school_id, created_at=_now(), updated_at=_now())
        db.add(section)
        db.flush()
    else:
        # Already linked to this class (same section id) — treat as duplicate.
        existing_link = (
            db.query(ClassSection)
            .filter(
                ClassSection.school_id == school_id,
                ClassSection.class_id == class_id,
                ClassSection.section_id == section.id,
                ClassSection.deleted_at.is_(None),
            )
            .first()
        )
        if existing_link is not None:
            raise AcademicError(409, "A section with this name already exists for the class")

    link = ClassSection(
        class_id=klass.id,
        section_id=section.id,
        medium_id=klass.medium_id,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(link)
    _commit(db)
    db.refresh(section)
    db.refresh(link)
    return {
        **_section_item(section),
        "class_id": klass.id,
        "class_name": klass.name,
        "medium_id": link.medium_id,
        "class_section_id": link.id,
    }


def update_section(db: Session, school_id: int, section_id: int, body: dict) -> dict:
    """Partial update. class_id reassigns a single ClassSection mapping when present."""
    row = _owned(db, Section, section_id, school_id)
    links = _section_class_links(db, school_id, section_id)
    name = row.name

    if "name" in body:
        name = _normalize_section_name(body["name"])
        if name.lower() != row.name.lower():
            for link in links:
                _assert_unique_section_name_in_class(
                    db, school_id, link.class_id, name, exclude_section_id=row.id
                )
            # Also check target class if reassignment is requested in the same PATCH.
            if "class_id" in body:
                target_class_id = int(body["class_id"])
                if not any(link.class_id == target_class_id for link in links):
                    _assert_unique_section_name_in_class(
                        db, school_id, target_class_id, name, exclude_section_id=row.id
                    )
        row.name = name

    if "class_id" in body:
        target_class_id = int(body["class_id"])
        klass = _owned(db, SchoolClass, target_class_id, school_id)
        _assert_unique_section_name_in_class(
            db, school_id, target_class_id, row.name, exclude_section_id=row.id
        )
        if not links:
            db.add(
                ClassSection(
                    class_id=klass.id,
                    section_id=row.id,
                    medium_id=klass.medium_id,
                    school_id=school_id,
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
        elif len(links) == 1:
            link = links[0]
            if link.class_id != klass.id:
                link.class_id = klass.id
                link.medium_id = klass.medium_id
                link.updated_at = _now()
        else:
            already = next((item for item in links if item.class_id == klass.id), None)
            if already is None:
                raise AcademicError(
                    422,
                    "Section is linked to multiple classes; use class-sections to change mappings",
                )
        row.updated_at = _now()
    elif "name" in body:
        row.updated_at = _now()

    _commit(db)
    db.refresh(row)
    return _section_detail(db, school_id, row)


def _class_item(row: SchoolClass) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "medium_id": row.medium_id,
        "include_semesters": row.include_semesters,
    }


def _normalize_class_name(name: str | None) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise AcademicError(422, "Class name is required")
    if len(cleaned) > 512:
        raise AcademicError(422, "Class name must be at most 512 characters")
    return cleaned


def _normalize_include_semesters(value) -> int:
    try:
        flag = int(value)
    except (TypeError, ValueError) as exc:
        raise AcademicError(422, "include_semesters must be 0 or 1") from exc
    if flag not in (0, 1):
        raise AcademicError(422, "include_semesters must be 0 or 1")
    return flag


def _assert_unique_class_name(
    db: Session,
    school_id: int,
    medium_id: int,
    name: str,
    *,
    exclude_id: int | None = None,
) -> None:
    """Active class names are unique per school + medium (case-insensitive)."""
    query = db.query(SchoolClass).filter(
        SchoolClass.school_id == school_id,
        SchoolClass.medium_id == medium_id,
        SchoolClass.deleted_at.is_(None),
        func.lower(SchoolClass.name) == name.lower(),
    )
    if exclude_id is not None:
        query = query.filter(SchoolClass.id != exclude_id)
    if query.first() is not None:
        raise AcademicError(409, "A class with this name already exists for the medium")


def get_class(db: Session, school_id: int, class_id: int) -> dict:
    """Class detail with linked sections and subjects (batch-loaded, school-scoped)."""
    row = _owned(db, SchoolClass, class_id, school_id)
    item = _class_item(row)

    section_rows = (
        db.query(ClassSection)
        .filter(
            ClassSection.school_id == school_id,
            ClassSection.class_id == class_id,
            ClassSection.deleted_at.is_(None),
        )
        .order_by(ClassSection.id.asc())
        .all()
    )
    section_ids = {link.section_id for link in section_rows}
    sections_by_id = {
        section.id: section
        for section in db.query(Section).filter(Section.id.in_(section_ids or {-1})).all()
    }
    item["sections"] = [
        {
            "id": link.id,
            "section_id": link.section_id,
            "section_name": sections_by_id[link.section_id].name
            if link.section_id in sections_by_id
            else None,
            "medium_id": link.medium_id,
        }
        for link in section_rows
    ]

    subject_rows = (
        db.query(ClassSubject)
        .filter(
            ClassSubject.school_id == school_id,
            ClassSubject.class_id == class_id,
            ClassSubject.deleted_at.is_(None),
        )
        .order_by(ClassSubject.id.asc())
        .all()
    )
    subject_ids = {link.subject_id for link in subject_rows}
    subjects_by_id = {
        subject.id: subject
        for subject in db.query(Subject).filter(Subject.id.in_(subject_ids or {-1})).all()
    }
    item["subjects"] = [
        {
            "id": link.id,
            "subject_id": link.subject_id,
            "subject_name": subjects_by_id[link.subject_id].name
            if link.subject_id in subjects_by_id
            else None,
        }
        for link in subject_rows
    ]
    return item


def create_class(db: Session, school_id: int, body: dict) -> dict:
    if "name" not in body or "medium_id" not in body:
        raise AcademicError(422, "name and medium_id are required")
    name = _normalize_class_name(body["name"])
    medium_id = int(body["medium_id"])
    include_semesters = _normalize_include_semesters(body.get("include_semesters") or 0)
    _same_school(db, Medium, medium_id, school_id, "Medium")
    _assert_unique_class_name(db, school_id, medium_id, name)
    row = SchoolClass(
        name=name,
        medium_id=medium_id,
        include_semesters=include_semesters,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _class_item(row)


def update_class(db: Session, school_id: int, class_id: int, body: dict) -> dict:
    """Partial update. Does not cascade to class_sections or class_subjects."""
    row = _owned(db, SchoolClass, class_id, school_id)
    name = row.name
    medium_id = row.medium_id
    include_semesters = row.include_semesters
    if "name" in body:
        name = _normalize_class_name(body["name"])
    if "medium_id" in body:
        medium_id = int(body["medium_id"])
        _same_school(db, Medium, medium_id, school_id, "Medium")
    if "include_semesters" in body:
        include_semesters = _normalize_include_semesters(body["include_semesters"])
    if name.lower() != row.name.lower() or medium_id != row.medium_id:
        _assert_unique_class_name(db, school_id, medium_id, name, exclude_id=row.id)
    row.name = name
    row.medium_id = medium_id
    row.include_semesters = include_semesters
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _class_item(row)


def _class_section_item(db: Session, row: ClassSection) -> dict:
    klass = db.get(SchoolClass, row.class_id)
    section = db.get(Section, row.section_id)
    class_name = klass.name if klass is not None else str(row.class_id)
    section_name = section.name if section is not None else str(row.section_id)
    return {
        "id": row.id,
        "class_id": row.class_id,
        "section_id": row.section_id,
        "medium_id": row.medium_id,
        "class_name": class_name if klass is not None else None,
        "section_name": section_name if section is not None else None,
        "name": f"{class_name} / {section_name}",
    }


def create_class_section(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, SchoolClass, int(body["class_id"]), school_id, "Class")
    _same_school(db, Section, int(body["section_id"]), school_id, "Section")
    _same_school(db, Medium, int(body["medium_id"]), school_id, "Medium")
    existing = (
        db.query(ClassSection)
        .filter(
            ClassSection.school_id == school_id,
            ClassSection.class_id == int(body["class_id"]),
            ClassSection.section_id == int(body["section_id"]),
            ClassSection.deleted_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        raise AcademicError(409, "This class and section are already linked")
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
    return _class_section_item(db, row)


def update_class_section(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, ClassSection, row_id, school_id)
    class_id = int(body["class_id"]) if "class_id" in body else row.class_id
    section_id = int(body["section_id"]) if "section_id" in body else row.section_id
    medium_id = int(body["medium_id"]) if "medium_id" in body else row.medium_id
    _same_school(db, SchoolClass, class_id, school_id, "Class")
    _same_school(db, Section, section_id, school_id, "Section")
    _same_school(db, Medium, medium_id, school_id, "Medium")
    clash = (
        db.query(ClassSection)
        .filter(
            ClassSection.school_id == school_id,
            ClassSection.class_id == class_id,
            ClassSection.section_id == section_id,
            ClassSection.deleted_at.is_(None),
            ClassSection.id != row.id,
        )
        .first()
    )
    if clash is not None:
        raise AcademicError(409, "This class and section are already linked")
    row.class_id = class_id
    row.section_id = section_id
    row.medium_id = medium_id
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _class_section_item(db, row)


def _normalize_subject_name(name: str | None) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise AcademicError(422, "Subject name is required")
    if len(cleaned) > 512:
        raise AcademicError(422, "Subject name must be at most 512 characters")
    return cleaned


def _normalize_subject_code(code: str | None, *, required: bool = False) -> str | None:
    if code is None:
        if required:
            raise AcademicError(422, "Subject code is required")
        return None
    cleaned = code.strip()
    if not cleaned:
        return None
    if len(cleaned) > 64:
        raise AcademicError(422, "Subject code must be at most 64 characters")
    return cleaned


def _normalize_subject_type(value: str | None) -> str:
    cleaned = (value or "Theory").strip()
    if cleaned not in SUBJECT_TYPES:
        raise AcademicError(422, "Subject type must be Theory or Practical")
    return cleaned


def _assert_unique_subject_code(
    db: Session,
    school_id: int,
    medium_id: int,
    code: str | None,
    *,
    exclude_id: int | None = None,
) -> None:
    """Active non-blank codes are unique per school + medium (case-insensitive)."""
    if code is None:
        return
    query = db.query(Subject).filter(
        Subject.school_id == school_id,
        Subject.medium_id == medium_id,
        Subject.deleted_at.is_(None),
        Subject.code.isnot(None),
        func.lower(Subject.code) == code.lower(),
    )
    if exclude_id is not None:
        query = query.filter(Subject.id != exclude_id)
    if query.first() is not None:
        raise AcademicError(409, "A subject with this code already exists for the medium")


def get_subject(db: Session, school_id: int, subject_id: int) -> dict:
    row = _owned(db, Subject, subject_id, school_id)
    item = _subject_item(row)
    links = (
        db.query(ClassSubject)
        .filter(
            ClassSubject.school_id == school_id,
            ClassSubject.subject_id == subject_id,
            ClassSubject.deleted_at.is_(None),
        )
        .order_by(ClassSubject.id.asc())
        .all()
    )
    class_ids = {link.class_id for link in links}
    classes_by_id = {
        klass.id: klass
        for klass in db.query(SchoolClass).filter(SchoolClass.id.in_(class_ids or {-1})).all()
    }
    item["classes"] = [
        {
            "class_id": link.class_id,
            "class_name": classes_by_id[link.class_id].name if link.class_id in classes_by_id else None,
            "medium_id": classes_by_id[link.class_id].medium_id if link.class_id in classes_by_id else None,
            "class_subject_id": link.id,
        }
        for link in links
    ]
    return item


def list_subject_classes(
    db: Session,
    school_id: int,
    subject_id: int,
    page: int,
    page_size: int,
) -> dict:
    _owned(db, Subject, subject_id, school_id)
    page, page_size = _page(page, page_size)
    query = db.query(ClassSubject).filter(
        ClassSubject.school_id == school_id,
        ClassSubject.subject_id == subject_id,
        ClassSubject.deleted_at.is_(None),
    )
    total = query.count()
    rows = query.order_by(ClassSubject.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    class_ids = {link.class_id for link in rows}
    classes_by_id = {
        klass.id: klass
        for klass in db.query(SchoolClass).filter(SchoolClass.id.in_(class_ids or {-1})).all()
    }
    items = [
        {
            "class_id": link.class_id,
            "class_name": classes_by_id[link.class_id].name if link.class_id in classes_by_id else None,
            "medium_id": classes_by_id[link.class_id].medium_id if link.class_id in classes_by_id else None,
            "class_subject_id": link.id,
        }
        for link in rows
    ]
    return _envelope(items, total, page, page_size)


def replace_subject_classes(db: Session, school_id: int, subject_id: int, class_ids: list[int]) -> dict:
    """Replace active class associations for a subject using soft-delete + revive.

    Soft-deleted historical ClassSubject rows are never hard-deleted. Desired
    classes that already have a soft-deleted mapping are revived. All target
    classes must belong to the school and match the subject's medium.
    """
    subject = _owned(db, Subject, subject_id, school_id)
    # Deduplicate while preserving order for stable responses.
    seen: set[int] = set()
    desired: list[int] = []
    for raw in class_ids:
        class_id = int(raw)
        if class_id in seen:
            continue
        seen.add(class_id)
        desired.append(class_id)

    classes_by_id: dict[int, SchoolClass] = {}
    for class_id in desired:
        klass = _owned(db, SchoolClass, class_id, school_id)
        if klass.medium_id != subject.medium_id:
            raise AcademicError(422, "Class medium does not match the subject medium")
        classes_by_id[class_id] = klass

    desired_set = set(desired)
    existing = (
        db.query(ClassSubject)
        .filter(ClassSubject.school_id == school_id, ClassSubject.subject_id == subject_id)
        .all()
    )
    now = _now()
    active_by_class = {
        row.class_id: row for row in existing if row.deleted_at is None
    }
    deleted_by_class = {
        row.class_id: row for row in existing if row.deleted_at is not None
    }

    for class_id, row in list(active_by_class.items()):
        if class_id not in desired_set:
            row.deleted_at = now
            row.updated_at = now

    for class_id in desired:
        if class_id in active_by_class:
            continue
        if class_id in deleted_by_class:
            row = deleted_by_class[class_id]
            row.deleted_at = None
            row.updated_at = now
            continue
        db.add(
            ClassSubject(
                school_id=school_id,
                class_id=class_id,
                subject_id=subject_id,
                created_at=now,
                updated_at=now,
            )
        )

    _commit(db)
    return list_subject_classes(db, school_id, subject_id, page=1, page_size=PAGE_SIZE_MAX)


def create_subject(db: Session, school_id: int, body: dict) -> dict:
    if "name" not in body or "medium_id" not in body:
        raise AcademicError(422, "name and medium_id are required")
    name = _normalize_subject_name(body["name"])
    medium_id = int(body["medium_id"])
    code = _normalize_subject_code(body.get("code"))
    subject_type = _normalize_subject_type(body.get("type"))
    _same_school(db, Medium, medium_id, school_id, "Medium")
    _assert_unique_subject_code(db, school_id, medium_id, code)
    row = Subject(
        name=name,
        code=code,
        type=subject_type,
        medium_id=medium_id,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _subject_item(row)


def update_subject(db: Session, school_id: int, subject_id: int, body: dict) -> dict:
    """Partial update. Does not change class_subjects mappings."""
    row = _owned(db, Subject, subject_id, school_id)
    name = row.name
    code = row.code
    subject_type = row.type
    medium_id = row.medium_id
    if "name" in body:
        name = _normalize_subject_name(body["name"])
    if "code" in body:
        code = _normalize_subject_code(body["code"])
    if "type" in body:
        subject_type = _normalize_subject_type(body["type"])
    if "medium_id" in body:
        medium_id = int(body["medium_id"])
        _same_school(db, Medium, medium_id, school_id, "Medium")
    code_changed = (code or "").lower() != (row.code or "").lower()
    medium_changed = medium_id != row.medium_id
    if code_changed or medium_changed:
        _assert_unique_subject_code(db, school_id, medium_id, code, exclude_id=row.id)
    row.name = name
    row.code = code
    row.type = subject_type
    row.medium_id = medium_id
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _subject_item(row)


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
    if kind == 0:
        try:
            from app.models.tables import AttendanceEvent
            from app.services.v1 import notification_delivery as notif

            now = _now()
            db.add(
                AttendanceEvent(
                    school_id=school_id,
                    attendance_id=row.id,
                    student_id=row.student_id,
                    session_year_id=row.session_year_id,
                    attendance_date=row.date,
                    event_type="absence",
                    status_type=0,
                    metadata_json=None,
                    created_at=now,
                    processed_at=None,
                )
            )
            _commit(db)
            notif.enqueue_student_absence(
                db,
                school_id,
                attendance_id=row.id,
                student_id=row.student_id,
                attendance_date=row.date,
            )
        except Exception:
            logger = __import__("logging").getLogger(__name__)
            logger.exception("absence_notification_enqueue_failed attendance_id=%s", row.id)
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
    """Academics/notices create — supports optional audience/status when provided."""
    import json as _json

    _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
    now = _now()
    status_val = str(body.get("status") or "published").strip().lower()
    if status_val not in {"draft", "scheduled", "published", "archived"}:
        status_val = "published"
    audience = body.get("audience") or ["all"]
    if isinstance(audience, str):
        audience = [audience]
    row = Announcement(
        title=body["title"].strip(),
        description=body.get("description"),
        session_year_id=int(body["session_year_id"]),
        school_id=school_id,
        status=status_val,
        audience_json=_json.dumps(list(audience)),
        published_at=now if status_val == "published" else None,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.title,
        "title": row.title,
        "description": row.description,
        "session_year_id": row.session_year_id,
        "status": row.status,
        "audience": audience,
    }


def _student_id_for_user(db: Session, school_id: int, user_id: int) -> int | None:
    student = (
        db.query(Student)
        .filter(
            Student.school_id == school_id,
            Student.user_id == user_id,
            Student.deleted_at.is_(None),
        )
        .first()
    )
    return student.id if student else None


def _resolve_leave_type_id(db: Session, school_id: int, body: dict) -> int | None:
    """Resolve leave_type_id or leave_type/code to a school-owned LeaveType.id."""
    if body.get("leave_type_id") is not None:
        lt = _owned(db, LeaveType, int(body["leave_type_id"]), school_id)
        if not lt.is_active:
            raise AcademicError(422, "Leave type is inactive")
        return lt.id
    code = body.get("leave_type") or body.get("leave_type_code")
    if code is None or str(code).strip() == "":
        return None
    key = str(code).strip()
    lt = (
        db.query(LeaveType)
        .filter(
            LeaveType.school_id == school_id,
            LeaveType.deleted_at.is_(None),
            LeaveType.code == key,
        )
        .first()
    )
    if lt is None:
        lt = (
            db.query(LeaveType)
            .filter(
                LeaveType.school_id == school_id,
                LeaveType.deleted_at.is_(None),
                LeaveType.name == key,
            )
            .first()
        )
    if lt is None:
        raise AcademicError(404, "Leave type not found")
    if not lt.is_active:
        raise AcademicError(422, "Leave type is inactive")
    return lt.id


def _leave_dict(db: Session, school_id: int, row: Leave) -> dict:
    leave_type = None
    leave_type_code = None
    if getattr(row, "leave_type_id", None):
        lt = db.get(LeaveType, row.leave_type_id)
        if lt is not None and lt.school_id == school_id and lt.deleted_at is None:
            leave_type = lt.name
            leave_type_code = lt.code
    return {
        "id": row.id,
        "name": row.reason,
        "user_id": row.user_id,
        "student_id": _student_id_for_user(db, school_id, row.user_id),
        "reason": row.reason,
        "from_date": row.from_date.isoformat(),
        "to_date": row.to_date.isoformat(),
        "status": row.status,
        "session_year_id": row.session_year_id,
        "leave_type_id": getattr(row, "leave_type_id", None),
        "leave_type": leave_type,
        "leave_type_code": leave_type_code,
        "decided_by_user_id": getattr(row, "decided_by_user_id", None),
        "decided_by_v1": getattr(row, "decided_by_v1", None),
        "decided_at": row.decided_at.isoformat() if getattr(row, "decided_at", None) else None,
    }


def _assert_leave_type_applies_to(
    db: Session, school_id: int, user_id: int, leave_type_id: int | None
) -> None:
    """Enforce LeaveType.applies_to against the requester role (student/staff/teacher)."""
    if leave_type_id is None:
        return
    lt = _owned(db, LeaveType, leave_type_id, school_id)
    applies = str(lt.applies_to or "all").strip().lower()
    if applies in ("", "all"):
        return
    is_student = _student_id_for_user(db, school_id, user_id) is not None
    is_staff = (
        db.query(Staff)
        .filter(Staff.school_id == school_id, Staff.user_id == user_id)
        .first()
        is not None
    )
    if applies in ("students", "student"):
        if not is_student:
            raise AcademicError(422, "This leave type applies only to students")
        return
    if applies in ("teachers", "teacher"):
        if not is_staff:
            raise AcademicError(422, "This leave type applies only to teachers")
        return
    if applies in ("staff",):
        if not is_staff:
            raise AcademicError(422, "This leave type applies only to staff")
        return
    raise AcademicError(422, f"Unsupported leave type applies_to value: {applies}")


def _record_leave_decision(
    row: Leave,
    *,
    actor_user_id: int | None = None,
    actor_v1: str | None = None,
) -> None:
    row.decided_by_user_id = int(actor_user_id) if actor_user_id is not None else None
    row.decided_by_v1 = str(actor_v1)[:36] if actor_v1 else None
    row.decided_at = _now()


LEAVE_STATUS_PENDING = 0
LEAVE_STATUS_APPROVED = 1
LEAVE_STATUS_REJECTED = 2
LEAVE_STATUS_CANCELLED = 3


def _leave_day_count(from_date, to_date) -> int:
    return (to_date - from_date).days + 1


def _assert_no_leave_overlap(
    db: Session,
    school_id: int,
    user_id: int,
    from_date,
    to_date,
    *,
    exclude_id: int | None = None,
) -> None:
    """Block overlapping pending/approved leaves for the same user."""
    q = db.query(Leave).filter(
        Leave.school_id == school_id,
        Leave.user_id == user_id,
        Leave.status.in_([LEAVE_STATUS_PENDING, LEAVE_STATUS_APPROVED]),
        Leave.from_date <= to_date,
        Leave.to_date >= from_date,
    )
    if exclude_id is not None:
        q = q.filter(Leave.id != exclude_id)
    if q.first() is not None:
        raise AcademicError(409, "Overlapping leave request already exists for these dates")


def _assert_leave_balance_allows(
    db: Session,
    school_id: int,
    user_id: int,
    leave_type_id: int | None,
    from_date,
    to_date,
    *,
    exclude_id: int | None = None,
) -> None:
    """When leave type has days_per_year, refuse approve/create that would exceed allowance."""
    if leave_type_id is None:
        return
    lt = _owned(db, LeaveType, leave_type_id, school_id)
    if lt.days_per_year is None:
        return
    yr = from_date.year
    year_start = from_date.replace(month=1, day=1)
    year_end = from_date.replace(month=12, day=31)
    used = 0
    rows = (
        db.query(Leave)
        .filter(
            Leave.school_id == school_id,
            Leave.user_id == user_id,
            Leave.leave_type_id == leave_type_id,
            Leave.status == LEAVE_STATUS_APPROVED,
            Leave.from_date <= year_end,
            Leave.to_date >= year_start,
        )
        .all()
    )
    for row in rows:
        if exclude_id is not None and row.id == exclude_id:
            continue
        a = max(row.from_date, year_start)
        b = min(row.to_date, year_end)
        if b >= a:
            used += (b - a).days + 1
    needed = _leave_day_count(from_date, to_date)
    if used + needed > int(lt.days_per_year):
        raise AcademicError(
            422,
            f"Insufficient leave balance for {lt.name}: allowed {lt.days_per_year}, used {used}, requested {needed}",
        )


def create_leave(db: Session, school_id: int, body: dict) -> dict:
    """Create leave for a school user.

    Accepts ``user_id`` (users.id) and/or ``student_id`` (students.id).
    When only ``student_id`` is sent, resolves to that student's ``user_id``.
    Never treats student_id as user_id.
    Optional ``leave_type_id`` or ``leave_type`` / ``leave_type_code``.
    New requests are always pending (status 0); clients cannot invent approved status.
    """
    raw_user_id = body.get("user_id")
    raw_student_id = body.get("student_id")
    user_id: int | None = int(raw_user_id) if raw_user_id is not None else None
    student_id: int | None = int(raw_student_id) if raw_student_id is not None else None

    if student_id is not None:
        student = _owned(db, Student, student_id, school_id)
        resolved = int(student.user_id)
        if user_id is not None and user_id != resolved:
            raise AcademicError(422, "student_id does not match user_id")
        user_id = resolved
    if user_id is None:
        raise AcademicError(422, "user_id or student_id is required")

    user = _same_school(db, User, user_id, school_id, "User")
    if not body.get("session_year_id"):
        raise AcademicError(422, "session_year_id is required")
    if not body.get("reason") or not str(body.get("reason")).strip():
        raise AcademicError(422, "reason is required")
    if body.get("from_date") is None or body.get("to_date") is None:
        raise AcademicError(422, "from_date and to_date are required")
    _same_school(db, SessionYear, int(body["session_year_id"]), school_id, "Session year")
    if body["to_date"] < body["from_date"]:
        raise AcademicError(422, "Leave end date must be on or after the start date")
    leave_type_id = _resolve_leave_type_id(db, school_id, body)
    _assert_leave_type_applies_to(db, school_id, user.id, leave_type_id)
    _assert_no_leave_overlap(db, school_id, user.id, body["from_date"], body["to_date"])
    _assert_leave_balance_allows(
        db, school_id, user.id, leave_type_id, body["from_date"], body["to_date"]
    )
    row = Leave(
        user_id=user.id,
        reason=str(body["reason"]).strip(),
        from_date=body["from_date"],
        to_date=body["to_date"],
        status=LEAVE_STATUS_PENDING,
        session_year_id=int(body["session_year_id"]),
        school_id=school_id,
        leave_type_id=leave_type_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _leave_dict(db, school_id, row)


def update_leave(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    """Partial leave update. Status transitions use approve/reject/cancel helpers."""
    row = _owned(db, Leave, row_id, school_id)
    data = dict(body)

    if int(row.status) in (LEAVE_STATUS_APPROVED, LEAVE_STATUS_REJECTED, LEAVE_STATUS_CANCELLED):
        if any(k in data for k in ("from_date", "to_date", "user_id", "student_id", "leave_type_id", "leave_type", "leave_type_code")):
            raise AcademicError(409, "Cannot modify dates or type after leave is finalized")

    raw_student_id = data.pop("student_id", None)
    if raw_student_id is not None:
        student = _owned(db, Student, int(raw_student_id), school_id)
        resolved = int(student.user_id)
        if "user_id" in data and data["user_id"] is not None and int(data["user_id"]) != resolved:
            raise AcademicError(422, "student_id does not match user_id")
        data["user_id"] = resolved

    if "user_id" in data and data["user_id"] is not None:
        user = _same_school(db, User, int(data["user_id"]), school_id, "User")
        row.user_id = user.id

    if "reason" in data:
        reason = str(data.get("reason") or "").strip()
        if not reason:
            raise AcademicError(422, "reason is required")
        row.reason = reason
    if "from_date" in data and data["from_date"] is not None:
        row.from_date = data["from_date"]
    if "to_date" in data and data["to_date"] is not None:
        row.to_date = data["to_date"]
    # Status changes only via dedicated approve/reject/cancel — never silently ignore.
    if "status" in data:
        raise AcademicError(
            422,
            "Leave status cannot be changed via PATCH. "
            "Use POST /academics/leaves/{id}/approve, /reject, or /cancel.",
        )
    if "session_year_id" in data and data["session_year_id"] is not None:
        _same_school(db, SessionYear, int(data["session_year_id"]), school_id, "Session year")
        row.session_year_id = int(data["session_year_id"])
    if any(k in data for k in ("leave_type_id", "leave_type", "leave_type_code")):
        if data.get("leave_type_id") is None and not data.get("leave_type") and not data.get(
            "leave_type_code"
        ):
            row.leave_type_id = None
        else:
            row.leave_type_id = _resolve_leave_type_id(db, school_id, data)

    if row.to_date < row.from_date:
        raise AcademicError(422, "Leave end date must be on or after the start date")
    if int(row.status) == LEAVE_STATUS_PENDING:
        _assert_no_leave_overlap(
            db, school_id, row.user_id, row.from_date, row.to_date, exclude_id=row.id
        )

    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _leave_dict(db, school_id, row)


def approve_leave(
    db: Session,
    school_id: int,
    row_id: int,
    *,
    actor_user_id: int | None = None,
    actor_v1: str | None = None,
) -> dict:
    row = _owned(db, Leave, row_id, school_id)
    if int(row.status) != LEAVE_STATUS_PENDING:
        raise AcademicError(409, "Only pending leave can be approved")
    _assert_leave_type_applies_to(db, school_id, row.user_id, row.leave_type_id)
    _assert_no_leave_overlap(
        db, school_id, row.user_id, row.from_date, row.to_date, exclude_id=row.id
    )
    _assert_leave_balance_allows(
        db,
        school_id,
        row.user_id,
        row.leave_type_id,
        row.from_date,
        row.to_date,
        exclude_id=row.id,
    )
    row.status = LEAVE_STATUS_APPROVED
    _record_leave_decision(row, actor_user_id=actor_user_id, actor_v1=actor_v1)
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    result = _leave_dict(db, school_id, row)
    result["action"] = "approved"
    result["actor_user_id"] = actor_user_id
    result["actor_v1"] = actor_v1
    try:
        from app.services.v1 import notification_delivery as notif

        queued = notif.enqueue_leave_decision(db, school_id, row, decision="approved")
        result["notification_id"] = queued.get("id")
    except Exception:
        import logging

        logging.getLogger(__name__).exception("leave_approve_notification_failed leave_id=%s", row.id)
        result["notification_id"] = None
    return result


def reject_leave(
    db: Session,
    school_id: int,
    row_id: int,
    *,
    actor_user_id: int | None = None,
    actor_v1: str | None = None,
) -> dict:
    row = _owned(db, Leave, row_id, school_id)
    if int(row.status) != LEAVE_STATUS_PENDING:
        raise AcademicError(409, "Only pending leave can be rejected")
    row.status = LEAVE_STATUS_REJECTED
    _record_leave_decision(row, actor_user_id=actor_user_id, actor_v1=actor_v1)
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    result = _leave_dict(db, school_id, row)
    result["action"] = "rejected"
    result["actor_user_id"] = actor_user_id
    result["actor_v1"] = actor_v1
    try:
        from app.services.v1 import notification_delivery as notif

        queued = notif.enqueue_leave_decision(db, school_id, row, decision="rejected")
        result["notification_id"] = queued.get("id")
    except Exception:
        import logging

        logging.getLogger(__name__).exception("leave_reject_notification_failed leave_id=%s", row.id)
        result["notification_id"] = None
    return result


def cancel_leave(
    db: Session,
    school_id: int,
    row_id: int,
    *,
    actor_user_id: int | None = None,
    actor_v1: str | None = None,
) -> dict:
    """Cancel pending leave (status=3). Approved leave cannot be cancelled here."""
    row = _owned(db, Leave, row_id, school_id)
    if int(row.status) != LEAVE_STATUS_PENDING:
        raise AcademicError(409, "Only pending leave can be cancelled")
    row.status = LEAVE_STATUS_CANCELLED
    _record_leave_decision(row, actor_user_id=actor_user_id, actor_v1=actor_v1)
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    result = _leave_dict(db, school_id, row)
    result["action"] = "cancelled"
    result["actor_user_id"] = actor_user_id
    result["actor_v1"] = actor_v1
    return result


def list_people(db: Session, school_id: int, kind: str, q: str, page: int, page_size: int) -> dict:
    if kind == "teachers":
        from app.services.v1 import school_teachers as teachers_svc

        return teachers_svc.list_teachers(db, school_id, q, page, page_size)

    page, page_size = _page(page, page_size)
    query = db.query(User).filter(User.school_id == school_id, User.deleted_at.is_(None))
    student_ids = {
        row[0]
        for row in db.query(Student.user_id)
        .filter(Student.school_id == school_id, Student.deleted_at.is_(None))
        .all()
    }
    staff_ids = {row[0] for row in db.query(Staff.user_id).filter(Staff.school_id == school_id).all()}
    if kind == "parents":
        if student_ids:
            query = query.filter(User.id.notin_(student_ids))
        if staff_ids:
            query = query.filter(User.id.notin_(staff_ids))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(User.first_name.ilike(like), User.last_name.ilike(like), User.email.ilike(like))
        )
    total = query.count()
    rows = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        {
            "id": row.id,
            "name": _user_name(row),
            "first_name": row.first_name,
            "last_name": row.last_name,
            "email": row.email,
            "mobile": row.mobile,
            "status": row.status,
        }
        for row in rows
    ]
    return _envelope(items, total, page, page_size)


def create_person(db: Session, school_id: int, kind: str, body: dict) -> dict:
    if kind == "teachers":
        from app.services.v1 import school_teachers as teachers_svc

        return teachers_svc.create_teacher(db, school_id, body)

    for field in ("first_name", "last_name", "email"):
        if field not in body or not str(body.get(field) or "").strip():
            raise AcademicError(422, f"{field} is required")
    email = str(body["email"]).strip().lower()
    _assert_unique_school_email(db, school_id, email)
    password_raw = body.get("password")
    if password_raw is None or not str(password_raw):
        raise AcademicError(422, "password is required")
    password = str(password_raw)
    if len(password) < 8:
        raise AcademicError(422, "password must be at least 8 characters")

    user = User(
        first_name=str(body["first_name"]).strip(),
        last_name=str(body["last_name"]).strip(),
        email=email,
        mobile=(body.get("mobile") or "").strip() or None,
        password=hash_password(password),
        status=1,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(user)
    db.flush()
    _commit(db)
    db.refresh(user)
    return {
        "id": user.id,
        "name": _user_name(user),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "mobile": user.mobile,
        "status": user.status,
    }


def soft_delete(db: Session, model, school_id: int, row_id: int) -> None:
    row = _owned(db, model, row_id, school_id)
    if hasattr(row, "deleted_at"):
        row.deleted_at = _now()
        if hasattr(row, "updated_at"):
            row.updated_at = _now()
    else:
        db.delete(row)
    _commit(db)


def _class_subject_item(db: Session, row: ClassSubject) -> dict:
    klass = db.get(SchoolClass, row.class_id)
    subject = db.get(Subject, row.subject_id)
    return {
        "id": row.id,
        "class_id": row.class_id,
        "subject_id": row.subject_id,
        "class_name": klass.name if klass is not None else None,
        "subject_name": subject.name if subject is not None else None,
        "name": f"{(klass.name if klass else row.class_id)} / {(subject.name if subject else row.subject_id)}",
    }


def list_class_subjects(
    db: Session,
    school_id: int,
    page: int,
    page_size: int,
    *,
    class_id: int | None = None,
    subject_id: int | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    query = db.query(ClassSubject).filter(
        ClassSubject.school_id == school_id, ClassSubject.deleted_at.is_(None)
    )
    if class_id is not None:
        query = query.filter(ClassSubject.class_id == class_id)
    if subject_id is not None:
        query = query.filter(ClassSubject.subject_id == subject_id)
    total = query.count()
    rows = query.order_by(ClassSubject.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_class_subject_item(db, row) for row in rows], total, page, page_size)


def create_class_subject(db: Session, school_id: int, body: dict) -> dict:
    _same_school(db, SchoolClass, int(body["class_id"]), school_id, "Class")
    _same_school(db, Subject, int(body["subject_id"]), school_id, "Subject")
    existing = (
        db.query(ClassSubject)
        .filter(
            ClassSubject.school_id == school_id,
            ClassSubject.class_id == int(body["class_id"]),
            ClassSubject.subject_id == int(body["subject_id"]),
            ClassSubject.deleted_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        raise AcademicError(409, "This subject is already mapped to the class")
    row = ClassSubject(
        school_id=school_id,
        class_id=int(body["class_id"]),
        subject_id=int(body["subject_id"]),
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _class_subject_item(db, row)


def update_class_subject(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, ClassSubject, row_id, school_id)
    class_id = int(body["class_id"]) if "class_id" in body else row.class_id
    subject_id = int(body["subject_id"]) if "subject_id" in body else row.subject_id
    _same_school(db, SchoolClass, class_id, school_id, "Class")
    _same_school(db, Subject, subject_id, school_id, "Subject")
    clash = (
        db.query(ClassSubject)
        .filter(
            ClassSubject.school_id == school_id,
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
            ClassSubject.deleted_at.is_(None),
            ClassSubject.id != row.id,
        )
        .first()
    )
    if clash is not None:
        raise AcademicError(409, "This subject is already mapped to the class")
    row.class_id = class_id
    row.subject_id = subject_id
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _class_subject_item(db, row)


def _staff_for_teacher_user(db: Session, school_id: int, teacher_user_id: int) -> Staff:
    from app.services.v1.school_teachers import _user_has_teacher_role

    user = db.get(User, teacher_user_id)
    if user is None or user.school_id != school_id or user.deleted_at is not None:
        raise AcademicError(422, "Teacher does not belong to this school")
    if getattr(user, "status", 1) != 1:
        raise AcademicError(422, "Teacher is not active")
    if not _user_has_teacher_role(db, teacher_user_id, school_id):
        raise AcademicError(422, "User is not a Teacher in this school")
    staff = (
        db.query(Staff)
        .filter(Staff.user_id == teacher_user_id, Staff.school_id == school_id)
        .first()
    )
    if staff is None:
        raise AcademicError(422, "Teacher does not belong to this school")
    return staff


def _assert_subject_mapped_to_class(db: Session, school_id: int, class_id: int, subject_id: int) -> None:
    mapped = (
        db.query(ClassSubject)
        .filter(
            ClassSubject.school_id == school_id,
            ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id,
            ClassSubject.deleted_at.is_(None),
        )
        .first()
    )
    if mapped is None:
        raise AcademicError(422, "Subject is not mapped to the selected class")


def _resolve_class_section_id(
    db: Session,
    school_id: int,
    body: dict,
    *,
    existing: int | None,
) -> int | None:
    """Resolve class_section_id from class_id+section_id and/or class_section_id."""
    has_class = "class_id" in body
    has_section = "section_id" in body
    class_id = body.get("class_id")
    section_id = body.get("section_id")
    if has_class or has_section:
        if class_id is None or section_id is None:
            raise AcademicError(422, "class_id and section_id must be provided together")
        class_id = int(class_id)
        section_id = int(section_id)
        _owned(db, SchoolClass, class_id, school_id)
        _same_school(db, Section, section_id, school_id, "Section")
        link = (
            db.query(ClassSection)
            .filter(
                ClassSection.school_id == school_id,
                ClassSection.class_id == class_id,
                ClassSection.section_id == section_id,
                ClassSection.deleted_at.is_(None),
            )
            .first()
        )
        if link is None:
            raise AcademicError(422, "Section is not linked to the selected class")
        if body.get("class_section_id") is not None and int(body["class_section_id"]) != link.id:
            raise AcademicError(422, "class_section_id does not match class_id and section_id")
        return link.id
    if "class_section_id" in body:
        if body["class_section_id"] is None:
            return None
        cs_id = int(body["class_section_id"])
        _same_school(db, ClassSection, cs_id, school_id, "Class section")
        return cs_id
    return existing


def _resolve_session_year_id(body: dict, *, existing: int | None) -> int | None:
    if "session_id" in body:
        return int(body["session_id"]) if body["session_id"] is not None else None
    if "session_year_id" in body:
        return int(body["session_year_id"]) if body["session_year_id"] is not None else None
    return existing


def _assignment_item(
    db: Session,
    row: TeacherAssignment,
    *,
    users: dict[int, User] | None = None,
    subjects: dict[int, Subject] | None = None,
    class_sections: dict[int, ClassSection] | None = None,
    classes: dict[int, SchoolClass] | None = None,
    sections: dict[int, Section] | None = None,
    sessions: dict[int, SessionYear] | None = None,
) -> dict:
    user = (users or {}).get(row.teacher_user_id) if users is not None else db.get(User, row.teacher_user_id)
    subject = (subjects or {}).get(row.subject_id) if subjects is not None else db.get(Subject, row.subject_id)
    link = None
    if row.class_section_id is not None:
        link = (
            (class_sections or {}).get(row.class_section_id)
            if class_sections is not None
            else db.get(ClassSection, row.class_section_id)
        )
    klass = classes.get(link.class_id) if classes is not None and link is not None else (
        db.get(SchoolClass, link.class_id) if link is not None else None
    )
    section = sections.get(link.section_id) if sections is not None and link is not None else (
        db.get(Section, link.section_id) if link is not None else None
    )
    session = None
    if row.session_year_id is not None:
        session = (
            (sessions or {}).get(row.session_year_id)
            if sessions is not None
            else db.get(SessionYear, row.session_year_id)
        )
    teacher_name = _user_name(user)
    subject_name = subject.name if subject is not None else None
    return {
        "id": row.id,
        "teacher_id": row.teacher_user_id,
        "staff_id": row.staff_id,
        "teacher_name": teacher_name,
        "subject_id": row.subject_id,
        "subject_name": subject_name,
        "class_section_id": row.class_section_id,
        "class_id": link.class_id if link is not None else None,
        "class_name": klass.name if klass is not None else None,
        "section_id": link.section_id if link is not None else None,
        "section_name": section.name if section is not None else None,
        "session_year_id": row.session_year_id,
        "session_id": row.session_year_id,
        "session_name": session.name if session is not None else None,
        "name": f"{teacher_name} / {(subject_name if subject_name else row.subject_id)}",
    }


def _assignment_items(db: Session, rows: list[TeacherAssignment]) -> list[dict]:
    if not rows:
        return []
    user_ids = {row.teacher_user_id for row in rows}
    subject_ids = {row.subject_id for row in rows}
    cs_ids = {row.class_section_id for row in rows if row.class_section_id is not None}
    session_ids = {row.session_year_id for row in rows if row.session_year_id is not None}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids or {-1})).all()}
    subjects = {s.id: s for s in db.query(Subject).filter(Subject.id.in_(subject_ids or {-1})).all()}
    class_sections = {
        cs.id: cs for cs in db.query(ClassSection).filter(ClassSection.id.in_(cs_ids or {-1})).all()
    }
    class_ids = {cs.class_id for cs in class_sections.values()}
    section_ids = {cs.section_id for cs in class_sections.values()}
    classes = {
        c.id: c for c in db.query(SchoolClass).filter(SchoolClass.id.in_(class_ids or {-1})).all()
    }
    sections = {
        s.id: s for s in db.query(Section).filter(Section.id.in_(section_ids or {-1})).all()
    }
    sessions = {
        sy.id: sy for sy in db.query(SessionYear).filter(SessionYear.id.in_(session_ids or {-1})).all()
    }
    return [
        _assignment_item(
            db,
            row,
            users=users,
            subjects=subjects,
            class_sections=class_sections,
            classes=classes,
            sections=sections,
            sessions=sessions,
        )
        for row in rows
    ]


def _find_open_assignment(
    db: Session,
    school_id: int,
    staff_id: int,
    subject_id: int,
    class_section_id: int | None,
    session_year_id: int | None,
    *,
    exclude_id: int | None = None,
) -> TeacherAssignment | None:
    query = db.query(TeacherAssignment).filter(
        TeacherAssignment.school_id == school_id,
        TeacherAssignment.staff_id == staff_id,
        TeacherAssignment.subject_id == subject_id,
        TeacherAssignment.deleted_at.is_(None),
    )
    if class_section_id is None:
        query = query.filter(TeacherAssignment.class_section_id.is_(None))
    else:
        query = query.filter(TeacherAssignment.class_section_id == class_section_id)
    if session_year_id is None:
        query = query.filter(TeacherAssignment.session_year_id.is_(None))
    else:
        query = query.filter(TeacherAssignment.session_year_id == session_year_id)
    if exclude_id is not None:
        query = query.filter(TeacherAssignment.id != exclude_id)
    return query.first()


def list_teacher_assignments(
    db: Session,
    school_id: int,
    page: int,
    page_size: int,
    *,
    teacher_id: int | None = None,
    subject_id: int | None = None,
    class_id: int | None = None,
    section_id: int | None = None,
    class_section_id: int | None = None,
    session_id: int | None = None,
    session_year_id: int | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    session_filter = session_id if session_id is not None else session_year_id
    query = db.query(TeacherAssignment).filter(
        TeacherAssignment.school_id == school_id, TeacherAssignment.deleted_at.is_(None)
    )
    if teacher_id is not None:
        query = query.filter(TeacherAssignment.teacher_user_id == teacher_id)
    if subject_id is not None:
        query = query.filter(TeacherAssignment.subject_id == subject_id)
    if class_section_id is not None:
        query = query.filter(TeacherAssignment.class_section_id == class_section_id)
    if session_filter is not None:
        query = query.filter(TeacherAssignment.session_year_id == session_filter)
    if class_id is not None or section_id is not None:
        if class_id is not None:
            _owned(db, SchoolClass, class_id, school_id)
        if section_id is not None:
            _same_school(db, Section, section_id, school_id, "Section")
        query = query.join(
            ClassSection,
            ClassSection.id == TeacherAssignment.class_section_id,
        ).filter(
            ClassSection.school_id == school_id,
            ClassSection.deleted_at.is_(None),
        )
        if class_id is not None:
            query = query.filter(ClassSection.class_id == class_id)
        if section_id is not None:
            query = query.filter(ClassSection.section_id == section_id)
    total = query.count()
    rows = (
        query.order_by(TeacherAssignment.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return _envelope(_assignment_items(db, rows), total, page, page_size)


def get_teacher_assignment(db: Session, school_id: int, row_id: int) -> dict:
    row = _owned(db, TeacherAssignment, row_id, school_id)
    return _assignment_items(db, [row])[0]


def soft_delete_teacher_assignment(db: Session, school_id: int, row_id: int) -> dict:
    """Soft-delete an assignment. No FK dependents on teacher_assignments today."""
    soft_delete(db, TeacherAssignment, school_id, row_id)
    return {"deleted": True}


def create_teacher_assignment(db: Session, school_id: int, body: dict) -> dict:
    if "teacher_id" not in body or "subject_id" not in body:
        raise AcademicError(422, "teacher_id and subject_id are required")
    staff = _staff_for_teacher_user(db, school_id, int(body["teacher_id"]))
    subject_id = int(body["subject_id"])
    _same_school(db, Subject, subject_id, school_id, "Subject")
    class_section_id = _resolve_class_section_id(db, school_id, body, existing=None)
    session_year_id = _resolve_session_year_id(body, existing=None)
    if session_year_id is not None:
        _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    if class_section_id is not None:
        link = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
        _assert_subject_mapped_to_class(db, school_id, link.class_id, subject_id)
    if _find_open_assignment(
        db, school_id, staff.id, subject_id, class_section_id, session_year_id
    ):
        raise AcademicError(409, "This teacher assignment already exists")
    row = TeacherAssignment(
        school_id=school_id,
        staff_id=staff.id,
        teacher_user_id=staff.user_id,
        subject_id=subject_id,
        class_section_id=class_section_id,
        session_year_id=session_year_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    _commit(db)
    db.refresh(row)
    return _assignment_items(db, [row])[0]


def update_teacher_assignment(db: Session, school_id: int, row_id: int, body: dict) -> dict:
    row = _owned(db, TeacherAssignment, row_id, school_id)
    teacher_user_id = int(body["teacher_id"]) if "teacher_id" in body else row.teacher_user_id
    subject_id = int(body["subject_id"]) if "subject_id" in body else row.subject_id
    class_section_id = _resolve_class_section_id(
        db, school_id, body, existing=row.class_section_id
    )
    session_year_id = _resolve_session_year_id(body, existing=row.session_year_id)
    staff = _staff_for_teacher_user(db, school_id, teacher_user_id)
    _same_school(db, Subject, subject_id, school_id, "Subject")
    if session_year_id is not None:
        _same_school(db, SessionYear, session_year_id, school_id, "Session year")
    if class_section_id is not None:
        link = _same_school(db, ClassSection, class_section_id, school_id, "Class section")
        _assert_subject_mapped_to_class(db, school_id, link.class_id, subject_id)
    if _find_open_assignment(
        db,
        school_id,
        staff.id,
        subject_id,
        class_section_id,
        session_year_id,
        exclude_id=row.id,
    ):
        raise AcademicError(409, "This teacher assignment already exists")
    row.staff_id = staff.id
    row.teacher_user_id = staff.user_id
    row.subject_id = subject_id
    row.class_section_id = class_section_id
    row.session_year_id = session_year_id
    row.updated_at = _now()
    _commit(db)
    db.refresh(row)
    return _assignment_items(db, [row])[0]
