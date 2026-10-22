"""School Admin people: students, parents, teachers, staff, photos and documents.

backend/docs/PEOPLE_API_CONTRACT.md. school_id always comes from the
authenticated admin. Rows from another school answer 404; ids from another
school inside a body answer 422 on that field. Rules and messages match
admin-web/lib/people/mock.ts.

A person is a legacy `users` row. Students add a `students` row, teachers and
staff a `staffs` row (employee_type), and parents are users linked through
`student_guardians` or holding the legacy Guardian role. Every person gets the
legacy role the mobile apps check at sign-in, and deactivating sets
users.status = 0, which those sign-ins refuse.
"""

from __future__ import annotations

import re
import secrets
from datetime import date
from pathlib import PurePath
from typing import Callable, Optional

from sqlalchemy import func, or_, select, union
from sqlalchemy.orm import Session, aliased

from app.core.security import hash_password
from app.models.tables import (
    USER_MODEL,
    ClassSection,
    Document,
    ModelHasRole,
    Role,
    SchoolClass,
    Section,
    SessionYear,
    Staff,
    Student,
    StudentGuardian,
    User,
)
from app.services.v1 import file_storage
from app.services.v1.records import (
    FieldErrors,
    RecordError,
    as_status,
    clean,
    commit,
    conflict,
    envelope,
    invalid,
    lock,
    not_found,
    now,
    optional,
    paging,
    status_filter,
    today,
    years_between,
)

RELATIONSHIPS = ("Father", "Mother", "Guardian", "Grandparent", "Sibling", "Other")
GENDERS = ("male", "female", "other")
EMPLOYMENT_TYPES = ("Permanent", "Probation", "Contract", "Part-time")
MAX_GUARDIANS = 4

EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MOBILE = re.compile(r"^\+?[0-9][0-9\s-]{6,18}$")
CODE = re.compile(r"^[A-Za-z0-9/-]+$")

# kind (URL segment) -> (staffs.employee_type, documents.owner_type, code prefix, legacy role)
EMPLOYEE_KINDS = {
    "teachers": ("teacher", "teacher", "TCH", "Teacher"),
    "staff": ("staff", "staff", "STF", "Staff"),
}

UrlFor = Callable[[str], str]


def _name(user: Optional[User]) -> str:
    return f"{user.first_name} {user.last_name}".strip() if user else ""


def _digits(value) -> str:
    return re.sub(r"\D", "", value or "")


def _like(q: str) -> str:
    return f"%{q.strip()}%"


def _iso(value) -> Optional[str]:
    return value.isoformat() if value else None


def _contact_email(user: User) -> Optional[str]:
    # Students without an email keep their admission number in users.email (legacy sign-in).
    return user.email if user.email and "@" in user.email else None


# ---------- shared checks ----------


def _check_name(errors: FieldErrors, prefix: str, body: dict) -> None:
    for field, label in (("first_name", "First name"), ("last_name", "Last name")):
        value = clean(body.get(field))
        if not value:
            errors.add(f"{prefix}{field}", f"{label} is required")
        elif len(value) > 128:
            errors.add(f"{prefix}{field}", f"{label} must be 128 characters or fewer")


def _check_email(errors: FieldErrors, field: str, value, required: bool) -> None:
    email = clean(value)
    if not email:
        if required:
            errors.add(field, "Email is required")
    elif len(email) > 255 or not EMAIL.match(email):
        errors.add(field, "Enter a valid email address")


def _check_mobile(errors: FieldErrors, field: str, value, required: bool) -> None:
    mobile = clean(value)
    if not mobile:
        if required:
            errors.add(field, "Phone number is required")
    elif not MOBILE.match(mobile) or not 7 <= len(_digits(mobile)) <= 15:
        errors.add(field, "Enter a valid phone number (7 to 15 digits)")


def _check_length(errors: FieldErrors, field: str, value, limit: int, label: str) -> None:
    if len(clean(value)) > limit:
        errors.add(field, f"{label} must be {limit} characters or fewer")


def _grant_role(db: Session, user_id: int, name: str, school_id: int) -> None:
    role = db.scalar(select(Role).where(Role.name == name, Role.guard_name == "web", Role.school_id == school_id))
    if role is None:
        role = Role(name=name, guard_name="web", school_id=school_id, created_at=now(), updated_at=now())
        db.add(role)
        db.flush()
    if db.get(ModelHasRole, (role.id, USER_MODEL, user_id)) is None:
        db.add(ModelHasRole(role_id=role.id, model_type=USER_MODEL, model_id=user_id))


def _parent_ids(school_id: int):
    """Users of the school who are parents: linked to a student or holding the Guardian role."""
    linked = select(StudentGuardian.parent_id.label("id")).where(StudentGuardian.school_id == school_id)
    role_holders = (
        select(ModelHasRole.model_id.label("id"))
        .join(Role, Role.id == ModelHasRole.role_id)
        .where(Role.name == "Guardian", Role.school_id == school_id, ModelHasRole.model_type == USER_MODEL)
    )
    return union(linked, role_holders).subquery()


def _person_label(db: Session, school_id: int, user: User) -> str:
    if db.scalar(select(Staff.id).where(Staff.user_id == user.id).limit(1)) is not None:
        return "a teacher or staff member"
    if db.scalar(select(Student.id).where(Student.user_id == user.id).limit(1)) is not None:
        return "a student"
    parents = _parent_ids(school_id)
    if db.scalar(select(parents.c.id).where(parents.c.id == user.id).limit(1)) is not None:
        return "a parent"
    return "another account"


def _email_user(db: Session, school_id: int, email: str, except_user_id: Optional[int] = None) -> Optional[User]:
    """Any user of the school (deleted ones too: users has a unique (school_id, email))."""
    query = select(User).where(User.school_id == school_id, func.lower(User.email) == email.lower())
    if except_user_id is not None:
        query = query.where(User.id != except_user_id)
    return db.scalar(query.limit(1))


def _email_taken(db: Session, school_id: int, email: str, except_user_id: Optional[int] = None) -> None:
    user = _email_user(db, school_id, email, except_user_id)
    if user is not None:
        conflict(f"{email} is already used by {_person_label(db, school_id, user)} in this school")


def _new_user(school_id: int, body: dict, email: str, status: int) -> User:
    return User(
        first_name=clean(body.get("first_name")),
        last_name=clean(body.get("last_name")),
        email=email,
        mobile=optional(body.get("mobile")),
        # Accounts are created without a usable password; sign-in is set up separately.
        password=hash_password(secrets.token_urlsafe(24)),
        status=status,
        school_id=school_id,
        created_at=now(),
        updated_at=now(),
    )


# ---------- files ----------


def _file_out(row: Document, url_for: UrlFor) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "file_name": row.file_name,
        "content_type": row.content_type,
        "size": row.size,
        "url": url_for(file_storage.sign(row.storage_key, row.content_type, row.file_name)),
        "uploaded_at": row.created_at.isoformat() + "Z",
    }


def _documents(db: Session, school_id: int, owner_type: str, owner_id: int, url_for: UrlFor) -> list[dict]:
    rows = db.scalars(
        select(Document)
        .where(
            Document.school_id == school_id,
            Document.owner_type == owner_type,
            Document.owner_id == owner_id,
            Document.kind == "document",
        )
        .order_by(Document.id)
    )
    return [_file_out(row, url_for) for row in rows]


def _photos(db: Session, school_id: int, owner_type: str, owner_ids: list[int], url_for: UrlFor) -> dict[int, str]:
    if not owner_ids:
        return {}
    rows = db.scalars(
        select(Document).where(
            Document.school_id == school_id,
            Document.owner_type == owner_type,
            Document.owner_id.in_(owner_ids),
            Document.kind == "photo",
        )
    )
    return {row.owner_id: url_for(file_storage.sign(row.storage_key, row.content_type, row.file_name)) for row in rows}


# ---------- students ----------


def _student_select():
    guardian = aliased(User)
    primary = aliased(StudentGuardian)
    return (
        select(Student, User, SessionYear.name, SchoolClass.id, SchoolClass.name, Section.name, guardian)
        .join(User, User.id == Student.user_id)
        .outerjoin(SessionYear, SessionYear.id == Student.session_year_id)
        .outerjoin(ClassSection, ClassSection.id == Student.class_section_id)
        .outerjoin(SchoolClass, SchoolClass.id == ClassSection.class_id)
        .outerjoin(Section, Section.id == ClassSection.section_id)
        .outerjoin(primary, (primary.student_id == Student.id) & primary.is_primary.is_(True))
        .outerjoin(guardian, guardian.id == primary.parent_id)
    )


def _student_rows(db: Session, school_id: int, rows, url_for: UrlFor) -> list[dict]:
    photos = _photos(db, school_id, "student", [row[0].id for row in rows], url_for)
    out = []
    for student, user, session_name, class_id, class_name, section_name, guardian in rows:
        out.append(
            {
                "id": student.id,
                "admission_no": student.admission_no,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "name": _name(user),
                "session_year_id": student.session_year_id,
                "session_name": session_name or "",
                "class_id": class_id or 0,
                "class_name": class_name or "",
                "class_section_id": student.class_section_id,
                "section_name": section_name or "",
                "roll_number": student.roll_number,
                "guardian_name": _name(guardian) or None,
                "guardian_mobile": guardian.mobile if guardian else None,
                "admission_date": _iso(student.admission_date),
                "photo_url": photos.get(student.id),
                "status": as_status(student.status),
            }
        )
    return out


STUDENT_SORTS = {"name", "admission_no", "admission_date", "class"}


def list_students(db: Session, school_id: int, params: dict, url_for: UrlFor) -> dict:
    page, page_size = paging(params.get("page", 1), params.get("page_size", 20))
    query = _student_select().where(Student.school_id == school_id, Student.deleted_at.is_(None))
    wanted = status_filter(params.get("status"))
    if wanted is not None:
        query = query.where(Student.status == wanted)
    for column, key in (
        (Student.session_year_id, "session_year_id"),
        (SchoolClass.id, "class_id"),
        (Student.class_section_id, "class_section_id"),
    ):
        if params.get(key):
            query = query.where(column == params[key])
    if params.get("parent_id"):
        linked = select(StudentGuardian.student_id).where(
            StudentGuardian.parent_id == params["parent_id"], StudentGuardian.school_id == school_id
        )
        query = query.where(Student.id.in_(linked))
    q = params.get("q") or ""
    if q.strip():
        like = _like(q)
        query = query.where(or_((User.first_name + " " + User.last_name).ilike(like), Student.admission_no.ilike(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    sort = params.get("sort") if params.get("sort") in STUDENT_SORTS else "name"
    keys = {
        "name": [func.lower(User.first_name), func.lower(User.last_name)],
        "admission_no": [func.length(Student.admission_no), Student.admission_no],
        "admission_date": [Student.admission_date],
        "class": [func.length(SchoolClass.name), SchoolClass.name, Section.name],
    }[sort]
    descending = params.get("order") == "desc"
    order = [key.desc() if descending else key.asc() for key in keys] + [Student.id]
    rows = db.execute(query.order_by(*order).offset((page - 1) * page_size).limit(page_size)).all()
    return envelope(_student_rows(db, school_id, rows, url_for), int(total), page, page_size)


def _own_student(db: Session, school_id: int, student_id: int, for_update: bool = False) -> Student:
    query = select(Student).where(Student.id == student_id, Student.school_id == school_id, Student.deleted_at.is_(None))
    if for_update:
        query = query.with_for_update()
    row = db.scalar(query)
    if row is None:
        not_found()
    return row


def _guardians(db: Session, student_id: int) -> list[dict]:
    rows = db.execute(
        select(StudentGuardian, User)
        .join(User, User.id == StudentGuardian.parent_id)
        .where(StudentGuardian.student_id == student_id)
        .order_by(StudentGuardian.is_primary.desc(), User.first_name, User.last_name)
    )
    return [
        {
            "parent_id": user.id,
            "name": _name(user),
            "email": user.email,
            "mobile": user.mobile,
            "relationship": link.relationship,
            "is_primary": bool(link.is_primary),
        }
        for link, user in rows
    ]


def student_profile(db: Session, school_id: int, student_id: int, url_for: UrlFor) -> dict:
    row = db.execute(
        _student_select().where(Student.id == student_id, Student.school_id == school_id, Student.deleted_at.is_(None))
    ).first()
    if row is None:
        not_found()
    out = _student_rows(db, school_id, [row], url_for)[0]
    user = row[1]
    out.update(
        {
            "dob": _iso(user.dob),
            "gender": user.gender,
            "email": _contact_email(user),
            "mobile": user.mobile,
            "current_address": user.current_address,
            "permanent_address": user.permanent_address,
            "guardians": _guardians(db, student_id),
            "documents": _documents(db, school_id, "student", student_id, url_for),
        }
    )
    return out


def _check_placement(db: Session, school_id: int, errors: FieldErrors, body: dict, current: Optional[Student]) -> None:
    session = db.get(SessionYear, body["session_year_id"]) if body.get("session_year_id") else None
    if session is None or session.school_id != school_id or session.deleted_at is not None:
        errors.add("session_year_id", "Choose an academic session from this school")
        session = None
    section = db.get(ClassSection, body["class_section_id"]) if body.get("class_section_id") else None
    if section is None or section.school_id != school_id or section.deleted_at is not None:
        errors.add("class_section_id", "Choose a section from this school")
        return
    if current is not None and current.class_section_id == section.id and current.session_year_id == body.get("session_year_id"):
        return  # an unchanged placement stays valid after its class or section is deactivated
    # classes and class_sections have no status or session column yet (see
    # ACADEMICS_API_CONTRACT.md); these checks apply once the columns exist.
    school_class = db.get(SchoolClass, section.class_id)
    class_session = getattr(school_class, "session_year_id", None)
    if school_class is None or school_class.deleted_at is not None or getattr(school_class, "status", 1) != 1:
        errors.add("class_section_id", "This class is inactive")
    elif getattr(section, "status", 1) != 1:
        errors.add("class_section_id", "This section is inactive")
    elif session is not None and class_session is not None and class_session != session.id:
        errors.add("class_section_id", f"{school_class.name} doesn't run in the {session.name} session")


def _check_student(db: Session, school_id: int, body: dict, errors: FieldErrors, current: Optional[Student] = None) -> None:
    _check_name(errors, "", body)
    dob = body.get("dob")
    if dob is None:
        errors.add("dob", "Enter the date of birth")
    elif dob > today():
        errors.add("dob", "Date of birth can't be in the future")
    elif not 2 <= years_between(dob, today()) <= 30:
        errors.add("dob", "Students must be between 2 and 30 years old")
    if body.get("gender") not in GENDERS:
        errors.add("gender", "Choose a gender")
    admission_date = body.get("admission_date")
    if admission_date is None:
        errors.add("admission_date", "Enter the admission date")
    elif dob is not None and admission_date <= dob:
        errors.add("admission_date", "Admission date must be after the date of birth")
    _check_placement(db, school_id, errors, body, current)
    admission_no = clean(body.get("admission_no"))
    if len(admission_no) > 32:
        errors.add("admission_no", "Admission number must be 32 characters or fewer")
    elif admission_no and not CODE.match(admission_no):
        errors.add("admission_no", "Use letters, numbers, - and / only")
    elif current is not None and not admission_no:
        errors.add("admission_no", "Admission number is required")
    roll = body.get("roll_number")
    if roll is not None and not 1 <= roll <= 9999:
        errors.add("roll_number", "Roll number must be a whole number from 1 to 9999")
    _check_email(errors, "email", body.get("email"), False)
    _check_mobile(errors, "mobile", body.get("mobile"), False)
    if not clean(body.get("current_address")):
        errors.add("current_address", "Address is required")
    else:
        _check_length(errors, "current_address", body.get("current_address"), 512, "Address")
    _check_length(errors, "permanent_address", body.get("permanent_address"), 512, "Address")


def _next_admission_no(db: Session, school_id: int, admission_date: date) -> str:
    prefix = f"ADM{admission_date.year}"
    used = db.scalars(
        select(Student.admission_no).where(Student.school_id == school_id, Student.admission_no.like(f"{prefix}%"))
    )
    numbers = [int(value[len(prefix):]) for value in used if value[len(prefix):].isdigit()]
    return f"{prefix}{max(numbers, default=0) + 1:04d}"


def _student_conflicts(db: Session, school_id: int, body: dict, admission_no: str, current: Optional[Student] = None) -> None:
    others = (
        select(Student, User)
        .join(User, User.id == Student.user_id)
        .where(Student.school_id == school_id, Student.deleted_at.is_(None))
    )
    if current is not None:
        others = others.where(Student.id != current.id)
    same_no = db.execute(others.where(func.lower(Student.admission_no) == admission_no.lower()).limit(1)).first()
    if same_no is not None:
        conflict(f"Admission number {admission_no} is already used by {_name(same_no[1])}")
    roll = body.get("roll_number")
    if roll:
        same_roll = db.execute(
            others.where(
                Student.session_year_id == body["session_year_id"],
                Student.class_section_id == body["class_section_id"],
                Student.roll_number == roll,
            ).limit(1)
        ).first()
        if same_roll is not None:
            conflict(f"Roll number {roll} is already used by {_name(same_roll[1])} in this section")
    email = clean(body.get("email"))
    if email:
        _email_taken(db, school_id, email, current.user_id if current is not None else None)
    # Without an email the admission number is the legacy sign-in name in users.email.
    elif _email_user(db, school_id, admission_no, current.user_id if current is not None else None) is not None:
        conflict(f"Admission number {admission_no} is already used as a sign-in name in this school")


def _eligible_parent(db: Session, school_id: int, parent_id) -> Optional[User]:
    """A live user of the school who isn't a student, teacher or staff member."""
    if parent_id is None:
        return None
    user = db.get(User, int(parent_id))
    if user is None or user.school_id != school_id or user.deleted_at is not None:
        return None
    if db.scalar(select(Staff.id).where(Staff.user_id == user.id).limit(1)) is not None:
        return None
    if db.scalar(select(Student.id).where(Student.user_id == user.id).limit(1)) is not None:
        return None
    return user


def _parent_query(school_id: int):
    parents = _parent_ids(school_id)
    return select(User).where(User.school_id == school_id, User.deleted_at.is_(None), User.id.in_(select(parents.c.id)))


def _duplicate_parent(db: Session, school_id: int, email: str, mobile: str, except_id: Optional[int] = None) -> Optional[User]:
    matches = []
    if email:
        matches.append(func.lower(User.email) == email.lower())
    if _digits(mobile):
        matches.append(func.regexp_replace(func.coalesce(User.mobile, ""), r"\D", "", "g") == _digits(mobile))
    if not matches:
        return None
    query = _parent_query(school_id).where(or_(*matches))
    if except_id is not None:
        query = query.where(User.id != except_id)
    return db.scalar(query.order_by(User.id).limit(1))


def _apply_student_user(user: User, body: dict, admission_no: str) -> None:
    user.first_name = clean(body.get("first_name"))
    user.last_name = clean(body.get("last_name"))
    email = optional(body.get("email"))
    user.email = email.lower() if email else admission_no
    user.mobile = optional(body.get("mobile"))
    user.dob = body.get("dob")
    user.gender = body.get("gender")
    user.current_address = clean(body.get("current_address"))
    user.permanent_address = optional(body.get("permanent_address"))
    user.status = as_status(body.get("status", 1))
    user.updated_at = now()


def create_student(db: Session, school_id: int, body: dict, url_for: UrlFor) -> dict:
    errors = FieldErrors()
    _check_student(db, school_id, body, errors)
    guardian = body.get("guardian")
    parent = None
    if not guardian:
        errors.add("guardian.parent_id", "Choose or add a parent or guardian")
    else:
        if guardian.get("relationship") not in RELATIONSHIPS:
            errors.add("guardian.relationship", "Choose the relationship")
        if guardian.get("parent_id") is not None:
            parent = _eligible_parent(db, school_id, guardian["parent_id"])
            if parent is None:
                errors.add("guardian.parent_id", "Choose a parent from this school")
        else:
            _check_name(errors, "guardian.", guardian)
            _check_email(errors, "guardian.email", guardian.get("email"), True)
            _check_mobile(errors, "guardian.mobile", guardian.get("mobile"), True)
    errors.raise_if_any()

    lock(db, "admission_no", school_id)
    admission_no = clean(body.get("admission_no")) or _next_admission_no(db, school_id, body["admission_date"])
    _student_conflicts(db, school_id, body, admission_no)
    if parent is None:
        email, mobile = clean(guardian.get("email")), clean(guardian.get("mobile"))
        duplicate = _duplicate_parent(db, school_id, email, mobile)
        if duplicate is not None:
            conflict(
                f"{_name(duplicate)} is already registered with this email or phone number. "
                "Choose them as an existing parent instead."
            )
        _email_taken(db, school_id, email)
        if clean(body.get("email")).lower() == email.lower():
            conflict(f"{email} can't be used for both the student and the guardian")
        parent = _new_user(school_id, guardian, email.lower(), 1)
        parent.current_address = clean(body.get("current_address"))
        db.add(parent)
        db.flush()

    user = User(password=hash_password(secrets.token_urlsafe(24)), school_id=school_id, created_at=now())
    _apply_student_user(user, body, admission_no)
    db.add(user)
    db.flush()
    student = Student(
        user_id=user.id,
        class_section_id=body["class_section_id"],
        admission_no=admission_no,
        roll_number=body.get("roll_number"),
        admission_date=body["admission_date"],
        school_id=school_id,
        guardian_id=parent.id,
        session_year_id=body["session_year_id"],
        status=user.status,
        created_at=now(),
        updated_at=now(),
    )
    db.add(student)
    db.flush()
    db.add(
        StudentGuardian(
            student_id=student.id,
            parent_id=parent.id,
            relationship=guardian["relationship"],
            is_primary=True,
            school_id=school_id,
            created_at=now(),
            updated_at=now(),
        )
    )
    _grant_role(db, user.id, "Student", school_id)
    _grant_role(db, parent.id, "Guardian", school_id)
    commit(db, f"Admission number {admission_no} or this roll number is already used")
    return student_profile(db, school_id, student.id, url_for)


def update_student(db: Session, school_id: int, student_id: int, body: dict, url_for: UrlFor) -> dict:
    student = _own_student(db, school_id, student_id, for_update=True)
    errors = FieldErrors()
    _check_student(db, school_id, body, errors, student)
    errors.raise_if_any()
    admission_no = clean(body.get("admission_no"))
    _student_conflicts(db, school_id, body, admission_no, student)
    user = db.get(User, student.user_id)
    _apply_student_user(user, body, admission_no)
    student.admission_no = admission_no
    student.roll_number = body.get("roll_number")
    student.admission_date = body["admission_date"]
    student.session_year_id = body["session_year_id"]
    student.class_section_id = body["class_section_id"]
    student.status = user.status
    student.updated_at = now()
    commit(db, f"Admission number {admission_no} or this roll number is already used")
    return student_profile(db, school_id, student.id, url_for)


def set_student_status(db: Session, school_id: int, student_id: int, status: int, url_for: UrlFor) -> dict:
    student = _own_student(db, school_id, student_id)
    user = db.get(User, student.user_id)
    student.status = user.status = as_status(status)
    student.updated_at = user.updated_at = now()
    commit(db)
    return student_profile(db, school_id, student.id, url_for)


def _set_primary(db: Session, student: Student, parent_id: int) -> None:
    links = list(db.scalars(select(StudentGuardian).where(StudentGuardian.student_id == student.id)))
    for link in links:
        if link.is_primary and link.parent_id != parent_id:
            link.is_primary = False
    db.flush()  # clear the old primary before the partial unique index sees the new one
    for link in links:
        if link.parent_id == parent_id:
            link.is_primary = True
    student.guardian_id = parent_id
    student.updated_at = now()


def link_guardian(db: Session, school_id: int, student_id: int, body: dict, url_for: UrlFor) -> dict:
    student = _own_student(db, school_id, student_id, for_update=True)
    errors = FieldErrors()
    parent = _eligible_parent(db, school_id, body.get("parent_id"))
    if parent is None:
        errors.add("parent_id", "Choose a parent from this school")
    if body.get("relationship") not in RELATIONSHIPS:
        errors.add("relationship", "Choose the relationship")
    errors.raise_if_any()
    student_user = db.get(User, student.user_id)
    links = list(db.scalars(select(StudentGuardian).where(StudentGuardian.student_id == student.id)))
    if any(link.parent_id == parent.id for link in links):
        conflict(f"{_name(parent)} is already linked to {_name(student_user)}")
    if len(links) >= MAX_GUARDIANS:
        conflict(f"{_name(student_user)} already has {MAX_GUARDIANS} guardians. Remove one before adding another.")
    db.add(
        StudentGuardian(
            student_id=student.id,
            parent_id=parent.id,
            relationship=body["relationship"],
            is_primary=False,
            school_id=school_id,
            created_at=now(),
            updated_at=now(),
        )
    )
    db.flush()
    if not links or body.get("is_primary"):
        _set_primary(db, student, parent.id)
    _grant_role(db, parent.id, "Guardian", school_id)
    commit(db, f"{_name(parent)} is already linked to {_name(student_user)}")
    return student_profile(db, school_id, student.id, url_for)


def unlink_guardian(db: Session, school_id: int, student_id: int, parent_id: int, url_for: UrlFor) -> dict:
    student = _own_student(db, school_id, student_id, for_update=True)
    links = list(db.scalars(select(StudentGuardian).where(StudentGuardian.student_id == student.id).order_by(StudentGuardian.id)))
    link = next((item for item in links if item.parent_id == parent_id), None)
    if link is None:
        not_found()
    if len(links) == 1:
        student_user = db.get(User, student.user_id)
        conflict(f"{_name(student_user)} must keep at least one parent or guardian. Link another one first.")
    was_primary = link.is_primary
    db.delete(link)
    db.flush()
    if was_primary:
        _set_primary(db, student, next(item for item in links if item is not link).parent_id)
    commit(db)
    return student_profile(db, school_id, student.id, url_for)


# ---------- parents ----------


def _children(db: Session, school_id: int, parent_ids: list[int]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {pid: [] for pid in parent_ids}
    if not parent_ids:
        return out
    rows = db.execute(
        select(StudentGuardian, Student, User, SchoolClass.name, Section.name)
        .join(Student, Student.id == StudentGuardian.student_id)
        .join(User, User.id == Student.user_id)
        .outerjoin(ClassSection, ClassSection.id == Student.class_section_id)
        .outerjoin(SchoolClass, SchoolClass.id == ClassSection.class_id)
        .outerjoin(Section, Section.id == ClassSection.section_id)
        .where(
            StudentGuardian.parent_id.in_(parent_ids),
            Student.school_id == school_id,
            Student.deleted_at.is_(None),
        )
        .order_by(User.first_name, User.last_name)
    )
    for link, student, user, class_name, section_name in rows:
        out[link.parent_id].append(
            {
                "student_id": student.id,
                "name": _name(user),
                "admission_no": student.admission_no,
                "class_name": class_name or "",
                "section_name": section_name or "",
                "relationship": link.relationship,
                "is_primary": bool(link.is_primary),
                "status": as_status(student.status),
            }
        )
    return out


def _parent_rows(db: Session, school_id: int, users: list[User]) -> list[dict]:
    children = _children(db, school_id, [user.id for user in users])
    return [
        {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "name": _name(user),
            "email": user.email,
            "mobile": user.mobile or "",
            "current_address": user.current_address,
            "occupation": user.occupation,
            "status": as_status(user.status),
            "children": children[user.id],
        }
        for user in users
    ]


def list_parents(db: Session, school_id: int, params: dict) -> dict:
    page, page_size = paging(params.get("page", 1), params.get("page_size", 20))
    query = _parent_query(school_id)
    wanted = status_filter(params.get("status"))
    if wanted is not None:
        query = query.where(User.status == wanted)
    email = clean(params.get("email"))
    if email:
        query = query.where(func.lower(User.email) == email.lower())
    mobile = _digits(params.get("mobile"))
    if mobile:
        query = query.where(func.regexp_replace(func.coalesce(User.mobile, ""), r"\D", "", "g") == mobile)
    q = params.get("q") or ""
    if q.strip():
        like = _like(q)
        query = query.where(
            or_((User.first_name + " " + User.last_name).ilike(like), User.email.ilike(like), User.mobile.ilike(like))
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    users = list(
        db.scalars(
            query.order_by(func.lower(User.first_name), func.lower(User.last_name), User.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return envelope(_parent_rows(db, school_id, users), int(total), page, page_size)


def _own_parent(db: Session, school_id: int, parent_id: int) -> User:
    user = db.scalar(_parent_query(school_id).where(User.id == parent_id))
    if user is None:
        not_found()
    return user


def parent_profile(db: Session, school_id: int, parent_id: int) -> dict:
    return _parent_rows(db, school_id, [_own_parent(db, school_id, parent_id)])[0]


def _check_parent(errors: FieldErrors, body: dict) -> None:
    _check_name(errors, "", body)
    _check_email(errors, "email", body.get("email"), True)
    _check_mobile(errors, "mobile", body.get("mobile"), True)
    _check_length(errors, "current_address", body.get("current_address"), 512, "Address")
    _check_length(errors, "occupation", body.get("occupation"), 255, "Occupation")


def _parent_conflicts(db: Session, school_id: int, body: dict, except_id: Optional[int] = None) -> None:
    email, mobile = clean(body.get("email")), clean(body.get("mobile"))
    duplicate = _duplicate_parent(db, school_id, email, mobile, except_id)
    if duplicate is not None:
        field = f"email {email}" if duplicate.email.lower() == email.lower() else f"phone number {mobile}"
        conflict(
            f"{_name(duplicate)} already has the {field}. "
            "Open their profile and link the student there instead of adding a new parent."
        )
    _email_taken(db, school_id, email, except_id)


def _apply_parent(user: User, body: dict) -> None:
    user.first_name = clean(body.get("first_name"))
    user.last_name = clean(body.get("last_name"))
    user.email = clean(body.get("email")).lower()
    user.mobile = clean(body.get("mobile"))
    user.current_address = optional(body.get("current_address"))
    user.occupation = optional(body.get("occupation"))
    user.status = as_status(body.get("status", 1))
    user.updated_at = now()


def create_parent(db: Session, school_id: int, body: dict) -> dict:
    errors = FieldErrors()
    _check_parent(errors, body)
    links = body.get("students") or []
    students: list[Student] = []
    for index, link in enumerate(links):
        student = db.scalar(
            select(Student).where(
                Student.id == link.get("student_id"), Student.school_id == school_id, Student.deleted_at.is_(None)
            )
        )
        if student is None:
            errors.add(("students", index, "student_id"), "Choose a student from this school")
            errors.add("students", "Choose students from this school")
        else:
            students.append(student)
        if link.get("relationship") not in RELATIONSHIPS:
            errors.add(("students", index, "relationship"), "Choose the relationship")
            errors.add("students", "Choose the relationship for each student")
    if len({link.get("student_id") for link in links}) != len(links):
        errors.add("students", "Each student can be linked once")
    errors.raise_if_any()
    _parent_conflicts(db, school_id, body)

    user = _new_user(school_id, body, clean(body.get("email")).lower(), as_status(body.get("status", 1)))
    _apply_parent(user, body)
    db.add(user)
    db.flush()
    _grant_role(db, user.id, "Guardian", school_id)
    for student, link in zip(students, links):
        student = _own_student(db, school_id, student.id, for_update=True)
        count = db.scalar(select(func.count(StudentGuardian.id)).where(StudentGuardian.student_id == student.id)) or 0
        if count >= MAX_GUARDIANS:
            db.rollback()
            student_user = db.get(User, student.user_id)
            conflict(f"{_name(student_user)} already has {MAX_GUARDIANS} guardians. Remove one before adding another.")
        db.add(
            StudentGuardian(
                student_id=student.id,
                parent_id=user.id,
                relationship=link["relationship"],
                is_primary=False,
                school_id=school_id,
                created_at=now(),
                updated_at=now(),
            )
        )
        db.flush()
        if count == 0:
            _set_primary(db, student, user.id)
    commit(db, f"{clean(body.get('email'))} is already used in this school")
    return parent_profile(db, school_id, user.id)


def update_parent(db: Session, school_id: int, parent_id: int, body: dict) -> dict:
    user = _own_parent(db, school_id, parent_id)
    errors = FieldErrors()
    _check_parent(errors, body)
    errors.raise_if_any()
    _parent_conflicts(db, school_id, body, user.id)
    _apply_parent(user, body)
    commit(db, f"{clean(body.get('email'))} is already used in this school")
    return parent_profile(db, school_id, user.id)


def set_parent_status(db: Session, school_id: int, parent_id: int, status: int) -> dict:
    user = _own_parent(db, school_id, parent_id)
    user.status = as_status(status)
    user.updated_at = now()
    commit(db)
    return parent_profile(db, school_id, user.id)


# ---------- teachers and staff ----------


def _employee_query(school_id: int, kind: str):
    employee_type = EMPLOYEE_KINDS[kind][0]
    return (
        select(User, Staff)
        .join(Staff, Staff.user_id == User.id)
        .where(
            Staff.school_id == school_id,
            Staff.employee_type == employee_type,
            User.school_id == school_id,
            User.deleted_at.is_(None),
        )
    )


def _employee_rows(db: Session, school_id: int, kind: str, rows, url_for: UrlFor) -> list[dict]:
    owner_type = EMPLOYEE_KINDS[kind][1]
    photos = _photos(db, school_id, owner_type, [user.id for user, _ in rows], url_for)
    return [
        {
            "id": user.id,
            "employee_code": staff.employee_code or "",
            "first_name": user.first_name,
            "last_name": user.last_name,
            "name": _name(user),
            "email": user.email,
            "mobile": user.mobile or "",
            "department": staff.department or "",
            "designation": staff.designation or "",
            "joining_date": _iso(staff.joining_date),
            "employment_type": staff.employment_type,
            "photo_url": photos.get(user.id),
            "status": as_status(user.status),
        }
        for user, staff in rows
    ]


def list_employees(db: Session, school_id: int, kind: str, params: dict, url_for: UrlFor) -> dict:
    page, page_size = paging(params.get("page", 1), params.get("page_size", 20))
    query = _employee_query(school_id, kind)
    wanted = status_filter(params.get("status"))
    if wanted is not None:
        query = query.where(User.status == wanted)
    department = clean(params.get("department"))
    if department:
        query = query.where(func.lower(Staff.department) == department.lower())
    if params.get("employment_type"):
        query = query.where(Staff.employment_type == params["employment_type"])
    q = params.get("q") or ""
    if q.strip():
        like = _like(q)
        query = query.where(
            or_(
                (User.first_name + " " + User.last_name).ilike(like),
                Staff.employee_code.ilike(like),
                User.email.ilike(like),
                User.mobile.ilike(like),
                Staff.designation.ilike(like),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(func.lower(User.first_name), func.lower(User.last_name), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return envelope(_employee_rows(db, school_id, kind, rows, url_for), int(total), page, page_size)


def list_departments(db: Session, school_id: int, kind: str) -> dict:
    names = db.scalars(
        select(Staff.department)
        .join(User, User.id == Staff.user_id)
        .where(
            Staff.school_id == school_id,
            Staff.employee_type == EMPLOYEE_KINDS[kind][0],
            User.deleted_at.is_(None),
            Staff.department.is_not(None),
            func.btrim(Staff.department) != "",
        )
        .distinct()
    )
    return {"items": sorted(set(names), key=str.lower)}


def _own_employee(db: Session, school_id: int, kind: str, user_id: int):
    row = db.execute(_employee_query(school_id, kind).where(User.id == user_id)).first()
    if row is None:
        not_found()
    return row


def employee_profile(db: Session, school_id: int, kind: str, user_id: int, url_for: UrlFor) -> dict:
    row = _own_employee(db, school_id, kind, user_id)
    out = _employee_rows(db, school_id, kind, [row], url_for)[0]
    user, staff = row
    out.update(
        {
            "gender": user.gender,
            "dob": _iso(user.dob),
            "qualification": staff.qualification,
            "current_address": user.current_address,
            "documents": _documents(db, school_id, EMPLOYEE_KINDS[kind][1], user.id, url_for),
        }
    )
    return out


def _check_employee(kind: str, body: dict, errors: FieldErrors, updating: bool) -> None:
    _check_name(errors, "", body)
    _check_email(errors, "email", body.get("email"), True)
    _check_mobile(errors, "mobile", body.get("mobile"), True)
    code = clean(body.get("employee_code"))
    if updating and not code:
        errors.add("employee_code", "Employee ID is required")
    elif len(code) > 32:
        errors.add("employee_code", "Employee ID must be 32 characters or fewer")
    elif code and not CODE.match(code):
        errors.add("employee_code", "Use letters, numbers, - and / only")
    for field, label in (("department", "Department"), ("designation", "Designation")):
        if not clean(body.get(field)):
            errors.add(field, f"{label} is required")
        else:
            _check_length(errors, field, body.get(field), 128, label)
    if kind == "teachers" and not clean(body.get("qualification")):
        errors.add("qualification", "Qualification is required for teachers")
    _check_length(errors, "qualification", body.get("qualification"), 512, "Qualification")
    joining = body.get("joining_date")
    if joining is None:
        errors.add("joining_date", "Enter the joining date")
    if body.get("employment_type") not in EMPLOYMENT_TYPES:
        errors.add("employment_type", "Choose the employment type")
    if body.get("gender") and body["gender"] not in GENDERS:
        errors.add("gender", "Choose a gender")
    dob = body.get("dob")
    if dob is not None:
        if years_between(dob, today()) < 18:
            errors.add("dob", "Employees must be at least 18 years old")
        elif joining is not None and joining <= dob:
            errors.add("joining_date", "Joining date must be after the date of birth")
    _check_length(errors, "current_address", body.get("current_address"), 512, "Address")


def _next_employee_code(db: Session, school_id: int, prefix: str) -> str:
    used = db.scalars(
        select(Staff.employee_code).where(Staff.school_id == school_id, func.upper(Staff.employee_code).like(f"{prefix}%"))
    )
    numbers = [int(value[len(prefix):]) for value in used if value and value[len(prefix):].isdigit()]
    return f"{prefix}{max(numbers, default=0) + 1:04d}"


def _employee_conflicts(db: Session, school_id: int, body: dict, code: str, except_user_id: Optional[int] = None) -> None:
    same_code = select(User).join(Staff, Staff.user_id == User.id).where(
        Staff.school_id == school_id, func.upper(Staff.employee_code) == code.upper()
    )
    if except_user_id is not None:
        same_code = same_code.where(User.id != except_user_id)
    holder = db.scalar(same_code.limit(1))
    if holder is not None:
        conflict(f"Employee ID {code} is already used by {_name(holder)}")
    _email_taken(db, school_id, clean(body.get("email")), except_user_id)


def _apply_employee(user: User, staff: Staff, body: dict, code: str) -> None:
    user.first_name = clean(body.get("first_name"))
    user.last_name = clean(body.get("last_name"))
    user.email = clean(body.get("email")).lower()
    user.mobile = clean(body.get("mobile"))
    user.gender = body.get("gender") or None
    user.dob = body.get("dob")
    user.current_address = optional(body.get("current_address"))
    user.status = as_status(body.get("status", 1))
    user.updated_at = now()
    staff.employee_code = code
    staff.qualification = optional(body.get("qualification"))
    staff.department = clean(body.get("department"))
    staff.designation = clean(body.get("designation"))
    staff.joining_date = body.get("joining_date")
    staff.employment_type = body.get("employment_type")
    staff.updated_at = now()


def create_employee(db: Session, school_id: int, kind: str, body: dict, url_for: UrlFor) -> dict:
    employee_type, _, prefix, role = EMPLOYEE_KINDS[kind]
    errors = FieldErrors()
    _check_employee(kind, body, errors, updating=False)
    errors.raise_if_any()
    lock(db, "employee_code", school_id)
    code = clean(body.get("employee_code")) or _next_employee_code(db, school_id, prefix)
    _employee_conflicts(db, school_id, body, code)
    user = User(password=hash_password(secrets.token_urlsafe(24)), school_id=school_id, created_at=now())
    staff = Staff(school_id=school_id, employee_type=employee_type, salary=0, created_at=now())
    _apply_employee(user, staff, body, code)
    db.add(user)
    db.flush()
    staff.user_id = user.id
    db.add(staff)
    _grant_role(db, user.id, role, school_id)
    commit(db, f"Employee ID {code} or this email is already used")
    return employee_profile(db, school_id, kind, user.id, url_for)


def update_employee(db: Session, school_id: int, kind: str, user_id: int, body: dict, url_for: UrlFor) -> dict:
    user, staff = _own_employee(db, school_id, kind, user_id)
    errors = FieldErrors()
    _check_employee(kind, body, errors, updating=True)
    errors.raise_if_any()
    code = clean(body.get("employee_code"))
    _employee_conflicts(db, school_id, body, code, user.id)
    _apply_employee(user, staff, body, code)
    commit(db, f"Employee ID {code} or this email is already used")
    return employee_profile(db, school_id, kind, user.id, url_for)


def set_employee_status(db: Session, school_id: int, kind: str, user_id: int, status: int, url_for: UrlFor) -> dict:
    user, _ = _own_employee(db, school_id, kind, user_id)
    user.status = as_status(status)
    user.updated_at = now()
    commit(db)
    return employee_profile(db, school_id, kind, user.id, url_for)


# ---------- uploads ----------

FILE_OWNERS = ("students", "teachers", "staff")


def _file_owner(db: Session, school_id: int, owner: str, owner_id: int) -> tuple[str, int]:
    if owner == "students":
        return "student", _own_student(db, school_id, owner_id).id
    if owner in EMPLOYEE_KINDS:
        user, _ = _own_employee(db, school_id, owner, owner_id)
        return EMPLOYEE_KINDS[owner][1], user.id
    not_found()


def _safe_file_name(name: Optional[str], content_type: str) -> str:
    base = PurePath((name or "").replace("\\", "/")).name
    base = re.sub(r"[\x00-\x1f\x7f\"<>]", "", base).strip()[:200]
    return base or f"file.{file_storage.EXTENSIONS.get(content_type, 'bin')}"


def _size_text(size: int) -> str:
    return f"{size / (1024 * 1024):.1f} MB" if size >= 1024 * 1024 else f"{max(1, round(size / 1024))} KB"


def _read_checked(data: bytes, limit: int, allowed: set[str], type_message: str) -> str:
    if not data:
        invalid("file", "This file is empty.")
    if len(data) > limit:
        raise RecordError(413, f"The file is larger than {_size_text(limit)}.")
    content_type = file_storage.sniff_type(data)
    if content_type not in allowed:
        raise RecordError(415, type_message)
    return content_type


def _store(db: Session, row: Document, data: bytes) -> None:
    storage = file_storage.get_storage()
    storage.save(row.storage_key, data)
    db.add(row)
    try:
        commit(db)
    except Exception:
        storage.delete(row.storage_key)
        raise


def upload_photo(db: Session, school_id: int, owner: str, owner_id: int, data: bytes, file_name: Optional[str], url_for: UrlFor) -> dict:
    owner_type, owner_key = _file_owner(db, school_id, owner, owner_id)
    content_type = _read_checked(
        data, file_storage.PHOTO_MAX_BYTES, file_storage.PHOTO_TYPES, "Only JPG, PNG and WebP images are allowed"
    )
    try:
        data = file_storage.reencode_image(data, content_type)
    except file_storage.StorageError as exc:
        raise RecordError(exc.status_code, exc.detail) from exc
    previous = list(
        db.scalars(
            select(Document).where(
                Document.school_id == school_id,
                Document.owner_type == owner_type,
                Document.owner_id == owner_key,
                Document.kind == "photo",
            )
        )
    )
    for old in previous:
        db.delete(old)
    row = Document(
        school_id=school_id,
        owner_type=owner_type,
        owner_id=owner_key,
        kind="photo",
        title="Photo",
        file_name=_safe_file_name(file_name, content_type),
        content_type=content_type,
        size=len(data),
        storage_key=file_storage.new_key(content_type),
        created_at=now(),
    )
    _store(db, row, data)
    storage = file_storage.get_storage()
    for old in previous:
        storage.delete(old.storage_key)
    return {"photo_url": url_for(file_storage.sign(row.storage_key, row.content_type, row.file_name))}


def upload_document(
    db: Session, school_id: int, owner: str, owner_id: int, data: bytes, file_name: Optional[str], title: Optional[str], url_for: UrlFor
) -> dict:
    owner_type, owner_key = _file_owner(db, school_id, owner, owner_id)
    if len(clean(title)) > 120:
        invalid("title", "Title must be 120 characters or fewer")
    content_type = _read_checked(
        data, file_storage.DOCUMENT_MAX_BYTES, file_storage.DOCUMENT_TYPES, "Only PDF, JPG and PNG files are allowed"
    )
    count = db.scalar(
        select(func.count(Document.id)).where(
            Document.school_id == school_id,
            Document.owner_type == owner_type,
            Document.owner_id == owner_key,
            Document.kind == "document",
        )
    ) or 0
    if count >= file_storage.DOCUMENTS_PER_RECORD:
        conflict(f"A record can hold up to {file_storage.DOCUMENTS_PER_RECORD} documents. Remove one first.")
    name = _safe_file_name(file_name, content_type)
    row = Document(
        school_id=school_id,
        owner_type=owner_type,
        owner_id=owner_key,
        kind="document",
        title=clean(title) or name,
        file_name=name,
        content_type=content_type,
        size=len(data),
        storage_key=file_storage.new_key(content_type),
        created_at=now(),
    )
    _store(db, row, data)
    return _file_out(row, url_for)


def delete_document(db: Session, school_id: int, owner: str, owner_id: int, document_id: int) -> dict:
    owner_type, owner_key = _file_owner(db, school_id, owner, owner_id)
    row = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.school_id == school_id,
            Document.owner_type == owner_type,
            Document.owner_id == owner_key,
            Document.kind == "document",
        )
    )
    if row is None:
        not_found()
    key = row.storage_key
    db.delete(row)
    commit(db)
    file_storage.get_storage().delete(key)
    return {"deleted": True}
