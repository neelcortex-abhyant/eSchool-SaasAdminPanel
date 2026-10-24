"""School-admin Students, Parents, and multi-guardian linking (People API).

Uses legacy ``users`` + ``students`` + ``student_guardians``. Account ``User.status``
(0|1) is the login gate exposed as ``status``. ``students.guardian_id`` stays in sync
with the primary ``student_guardians`` row.
"""

from __future__ import annotations

import re
import secrets
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tables import (
    USER_MODEL,
    ClassSection,
    ModelHasRole,
    PersonDocument,
    Role,
    School,
    SchoolClass,
    Section,
    SessionYear,
    Staff,
    Student,
    StudentGuardian,
    User,
)
from app.services.mobile_auth import revoke_legacy_user_tokens
from app.services.v1.school_academics import (
    AcademicError,
    _assert_unique_school_email,
    _assign_user_role,
    _commit,
    _ensure_school_role,
    _envelope,
    _now,
    _owned,
    _page,
    _same_school,
    _user_name,
)

GUARDIAN_ROLE = "Guardian"
RELATIONSHIPS = frozenset(
    {"Father", "Mother", "Guardian", "Grandparent", "Sibling", "Other"}
)
GENDERS = frozenset({"male", "female", "other"})
MAX_GUARDIANS = 4
ADMISSION_NO_RE = re.compile(r"^[A-Za-z0-9\-/]{1,32}$")
MOBILE_RE = re.compile(r"^\d{7,15}$")
SORT_FIELDS = frozenset({"name", "admission_no", "admission_date", "class"})
# Stored when client omits email (users.email is NOT NULL + unique per school).
# Never returned in People API responses — exposed as null instead.
_INTERNAL_EMAIL_SUFFIX = ".eschool.internal"
# Current + legacy placeholders (older creates used @{school_id}.internal).
_INTERNAL_EMAIL_RE = re.compile(
    r"^student\.[0-9a-f]+@\d+\.(?:eschool\.)?internal$"
)


def _is_internal_student_email(email: str | None) -> bool:
    if not email:
        return False
    return bool(_INTERNAL_EMAIL_RE.match(str(email).strip().lower()))


def _public_student_email(user: User) -> str | None:
    email = (user.email or "").strip()
    if not email or _is_internal_student_email(email):
        return None
    return user.email


def _placeholder_student_email(school_id: int) -> str:
    return f"student.{secrets.token_hex(8)}@{school_id}{_INTERNAL_EMAIL_SUFFIX}"


def _digits_only(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _require_str(body: dict, field: str, *, max_len: int) -> str:
    raw = body.get(field)
    if raw is None or not str(raw).strip():
        raise AcademicError(422, f"{field} is required")
    cleaned = str(raw).strip()
    if len(cleaned) > max_len:
        raise AcademicError(422, f"{field} must be at most {max_len} characters")
    return cleaned


def _opt_str(body: dict, field: str, *, max_len: int) -> str | None:
    if field not in body or body.get(field) is None:
        return None
    cleaned = str(body.get(field) or "").strip()
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        raise AcademicError(422, f"{field} must be at most {max_len} characters")
    return cleaned


def _parse_date(raw: Any, field: str) -> date:
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    text = str(raw or "").strip()
    if not text:
        raise AcademicError(422, f"{field} is required")
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise AcademicError(422, f"{field} must be a valid ISO date (YYYY-MM-DD)") from exc


def _parse_opt_date(raw: Any, field: str) -> date | None:
    if raw is None or raw == "":
        return None
    return _parse_date(raw, field)


def _normalize_gender(raw: Any, *, required: bool = True) -> str | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if required:
            raise AcademicError(422, "gender is required")
        return None
    value = str(raw).strip().lower()
    if value not in GENDERS:
        raise AcademicError(422, "gender must be male, female or other")
    return value


def _normalize_relationship(raw: Any) -> str:
    value = str(raw or "").strip()
    # Accept case-insensitive match to contract enum.
    for allowed in RELATIONSHIPS:
        if value.lower() == allowed.lower():
            return allowed
    raise AcademicError(
        422,
        "relationship must be one of: Father, Mother, Guardian, Grandparent, Sibling, Other",
    )


def _normalize_mobile(raw: Any, *, required: bool) -> str | None:
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        if required:
            raise AcademicError(422, "mobile is required")
        return None
    digits = _digits_only(str(raw))
    if not MOBILE_RE.match(digits):
        raise AcademicError(422, "mobile must contain 7 to 15 digits")
    return digits


def _normalize_email(raw: Any, *, required: bool) -> str | None:
    if raw is None or (isinstance(raw, str) and not str(raw).strip()):
        if required:
            raise AcademicError(422, "email is required")
        return None
    email = str(raw).strip().lower()
    if "@" not in email or len(email) > 255:
        raise AcademicError(422, "email is invalid")
    return email


def _validate_dob(dob: date) -> None:
    today = date.today()
    if dob > today:
        raise AcademicError(422, "dob cannot be in the future")
    age_days = (today - dob).days
    if age_days < 2 * 365 or age_days > 30 * 365 + 30:
        raise AcademicError(422, "student must be between 2 and 30 years old")


def _photo_url(user: User | None) -> str | None:
    if user is None or not user.image:
        return None
    return str(user.image)


def _doc_url(owner_kind: str, route_owner_id: int, document_id: int) -> str:
    """route_owner_id is student.id for students, users.id for teacher/staff."""
    if owner_kind == "student":
        return f"/api/v1/school-admin/students/{route_owner_id}/documents/{document_id}/download"
    if owner_kind == "teacher":
        return f"/api/v1/school-admin/teachers/{route_owner_id}/documents/{document_id}/download"
    return f"/api/v1/school-admin/staff/{route_owner_id}/documents/{document_id}/download"


def document_public_item(
    row: PersonDocument, *, owner_kind: str, route_owner_id: int
) -> dict:
    title = (row.title or row.original_filename or row.category or "Document").strip()
    return {
        "id": row.id,
        "title": title[:120],
        "file_name": row.original_filename,
        "content_type": row.content_type,
        "size": row.size_bytes,
        "url": _doc_url(owner_kind, route_owner_id, row.id),
        "uploaded_at": row.created_at.isoformat() + "Z" if row.created_at else None,
        # Backward-compatible fields for existing teacher/staff clients.
        "category": row.category,
        "size_bytes": row.size_bytes,
        "original_filename": row.original_filename,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _class_section_names(
    db: Session, school_id: int, class_section_id: int
) -> tuple[int | None, str | None, str | None]:
    cs = (
        db.query(ClassSection)
        .filter(
            ClassSection.id == class_section_id,
            ClassSection.school_id == school_id,
            ClassSection.deleted_at.is_(None),
        )
        .first()
    )
    if cs is None:
        return None, None, None
    klass = db.get(SchoolClass, cs.class_id)
    section = db.get(Section, cs.section_id)
    class_name = klass.name if klass and klass.deleted_at is None else None
    section_name = section.name if section and section.deleted_at is None else None
    return cs.class_id, class_name, section_name


def _session_name(db: Session, school_id: int, session_year_id: int) -> str | None:
    row = (
        db.query(SessionYear)
        .filter(
            SessionYear.id == session_year_id,
            SessionYear.school_id == school_id,
            SessionYear.deleted_at.is_(None),
        )
        .first()
    )
    return row.name if row else None


def _assert_active_class_section(
    db: Session, school_id: int, class_section_id: int, session_year_id: int
) -> ClassSection:
    cs = _same_school(db, ClassSection, class_section_id, school_id, "class_section_id")
    klass = db.get(SchoolClass, cs.class_id)
    section = db.get(Section, cs.section_id)
    if (
        klass is None
        or klass.school_id != school_id
        or klass.deleted_at is not None
        or section is None
        or section.school_id != school_id
        or section.deleted_at is not None
    ):
        raise AcademicError(422, "class_section_id must reference an active class and section")
    _same_school(db, SessionYear, session_year_id, school_id, "session_year_id")
    return cs


def _assert_admission_no_unique(
    db: Session, school_id: int, admission_no: str, *, exclude_student_id: int | None = None
) -> None:
    key = admission_no.strip().lower()
    query = db.query(Student, User).join(User, User.id == Student.user_id).filter(
        Student.school_id == school_id,
        Student.deleted_at.is_(None),
        func.lower(func.btrim(Student.admission_no)) == key,
    )
    if exclude_student_id is not None:
        query = query.filter(Student.id != exclude_student_id)
    row = query.first()
    if row is not None:
        student, user = row
        raise AcademicError(
            409,
            f"Admission number {admission_no} is already used by {_user_name(user) or student.admission_no}",
        )


def _assert_roll_unique(
    db: Session,
    school_id: int,
    session_year_id: int,
    class_section_id: int,
    roll_number: int | None,
    *,
    exclude_student_id: int | None = None,
) -> None:
    if roll_number is None:
        return
    query = db.query(Student).filter(
        Student.school_id == school_id,
        Student.session_year_id == session_year_id,
        Student.class_section_id == class_section_id,
        Student.roll_number == roll_number,
        Student.deleted_at.is_(None),
    )
    if exclude_student_id is not None:
        query = query.filter(Student.id != exclude_student_id)
    if query.first() is not None:
        raise AcademicError(409, "Roll number is already used in this class section and session")


def _lock_school_for_admission(db: Session, school_id: int) -> None:
    """Serialize admission-number allocation (works with zero existing students).

    Locks the school row and takes a transactional advisory lock so concurrent
    creates in the same school cannot allocate the same ADM sequence.
    """
    school = (
        db.query(School)
        .filter(School.id == school_id)
        .with_for_update()
        .first()
    )
    if school is None:
        raise AcademicError(422, "School not found")
    # Extra serialization on Postgres/Neon (school-row lock already held).
    bind = db.get_bind()
    if bind is not None and getattr(bind.dialect, "name", "") == "postgresql":
        lock_key = (int(school_id) & 0x7FFFFFFF) ^ 0x41444D00
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})


def _generate_admission_no(db: Session, school_id: int, admission_date: date) -> str:
    _lock_school_for_admission(db, school_id)
    year = admission_date.year
    prefix = f"ADM{year}"
    like = f"{prefix}%"
    existing = (
        db.query(Student.admission_no)
        .filter(
            Student.school_id == school_id,
            Student.admission_no.ilike(like),
            Student.deleted_at.is_(None),
        )
        .all()
    )
    max_seq = 0
    for (adm,) in existing:
        suffix = str(adm)[len(prefix) :]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:04d}"


def _primary_guardian_link(db: Session, student_id: int) -> StudentGuardian | None:
    return (
        db.query(StudentGuardian)
        .filter(
            StudentGuardian.student_id == student_id,
            StudentGuardian.deleted_at.is_(None),
            StudentGuardian.is_primary == 1,
        )
        .first()
    )


def _active_guardian_links(db: Session, student_id: int) -> list[StudentGuardian]:
    return (
        db.query(StudentGuardian)
        .filter(
            StudentGuardian.student_id == student_id,
            StudentGuardian.deleted_at.is_(None),
        )
        .order_by(StudentGuardian.is_primary.desc(), StudentGuardian.id.asc())
        .all()
    )


def _sync_legacy_guardian_id(db: Session, student: Student) -> None:
    primary = _primary_guardian_link(db, student.id)
    if primary is not None:
        student.guardian_id = primary.guardian_user_id


def _guardian_items(db: Session, student_id: int) -> list[dict]:
    items = []
    for link in _active_guardian_links(db, student_id):
        parent = db.get(User, link.guardian_user_id)
        if parent is None or parent.deleted_at is not None:
            continue
        items.append(
            {
                "parent_id": parent.id,
                "name": _user_name(parent),
                "email": parent.email,
                "mobile": parent.mobile,
                "relationship": link.relationship_type,
                "is_primary": bool(link.is_primary),
            }
        )
    return items


def _student_documents(
    db: Session, school_id: int, *, student_id: int, user_id: int
) -> list[dict]:
    rows = (
        db.query(PersonDocument)
        .filter(
            PersonDocument.school_id == school_id,
            PersonDocument.owner_user_id == user_id,
            PersonDocument.deleted_at.is_(None),
            PersonDocument.category != "profile_photo",
        )
        .order_by(PersonDocument.id.desc())
        .all()
    )
    return [
        document_public_item(row, owner_kind="student", route_owner_id=student_id)
        for row in rows
    ]


def _student_list_row(db: Session, school_id: int, student: Student, user: User) -> dict:
    class_id, class_name, section_name = _class_section_names(
        db, school_id, student.class_section_id
    )
    primary = _primary_guardian_link(db, student.id)
    guardian = db.get(User, primary.guardian_user_id) if primary else db.get(User, student.guardian_id)
    return {
        "id": student.id,
        "admission_no": student.admission_no,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "name": _user_name(user),
        "session_year_id": student.session_year_id,
        "session_name": _session_name(db, school_id, student.session_year_id),
        "class_id": class_id,
        "class_name": class_name,
        "class_section_id": student.class_section_id,
        "section_name": section_name,
        "roll_number": student.roll_number,
        "guardian_name": _user_name(guardian),
        "guardian_mobile": guardian.mobile if guardian else None,
        "admission_date": student.admission_date.isoformat() if student.admission_date else None,
        "photo_url": _photo_url(user),
        "status": int(user.status or 0),
    }


def _student_profile(db: Session, school_id: int, student: Student, user: User) -> dict:
    item = _student_list_row(db, school_id, student, user)
    item.update(
        {
            "dob": user.dob.isoformat() if user.dob else None,
            "gender": (user.gender or "").strip().lower() or None,
            "email": _public_student_email(user),
            "mobile": user.mobile,
            "current_address": user.current_address,
            "permanent_address": user.permanent_address,
            "guardians": _guardian_items(db, student.id),
            "documents": _student_documents(
                db, school_id, student_id=student.id, user_id=user.id
            ),
        }
    )
    return item


def _owned_student(db: Session, school_id: int, student_id: int) -> tuple[Student, User]:
    student = _owned(db, Student, student_id, school_id)
    user = db.get(User, student.user_id)
    if user is None or user.school_id != school_id or user.deleted_at is not None:
        raise AcademicError(404, "Record not found")
    return student, user


def _user_has_role(db: Session, user_id: int, school_id: int, role_name: str) -> bool:
    row = db.execute(
        select(ModelHasRole.role_id)
        .join(Role, Role.id == ModelHasRole.role_id)
        .where(
            ModelHasRole.model_id == user_id,
            ModelHasRole.model_type == USER_MODEL,
            Role.name == role_name,
            Role.school_id == school_id,
            Role.guard_name == "web",
        )
        .limit(1)
    ).first()
    return row is not None


def _owned_parent(db: Session, school_id: int, parent_id: int) -> User:
    user = db.get(User, parent_id)
    if (
        user is None
        or user.school_id != school_id
        or user.deleted_at is not None
        or not _user_has_role(db, user.id, school_id, GUARDIAN_ROLE)
    ):
        raise AcademicError(404, "Record not found")
    # Reject if this user is a student or staff account.
    if db.query(Student.id).filter(Student.user_id == user.id, Student.deleted_at.is_(None)).first():
        raise AcademicError(404, "Record not found")
    if db.query(Staff.id).filter(Staff.user_id == user.id, Staff.school_id == school_id).first():
        raise AcademicError(404, "Record not found")
    return user


def _assert_parent_contact_unique(
    db: Session,
    school_id: int,
    *,
    email: str,
    mobile: str,
    exclude_user_id: int | None = None,
) -> None:
    email_q = db.query(User).filter(
        User.school_id == school_id,
        func.lower(User.email) == email.lower(),
        User.deleted_at.is_(None),
    )
    if exclude_user_id is not None:
        email_q = email_q.filter(User.id != exclude_user_id)
    existing_email = email_q.first()
    if existing_email is not None:
        if _user_has_role(db, existing_email.id, school_id, GUARDIAN_ROLE):
            raise AcademicError(
                409,
                f"{_user_name(existing_email)} is already registered with this email or phone number. "
                "Choose them as an existing parent instead.",
            )
        raise AcademicError(
            409,
            f"Email is already used by {_user_name(existing_email)}. Link students on their record instead.",
        )

    mobile_q = db.query(User).filter(
        User.school_id == school_id,
        User.deleted_at.is_(None),
        User.mobile.isnot(None),
    )
    if exclude_user_id is not None:
        mobile_q = mobile_q.filter(User.id != exclude_user_id)
    for other in mobile_q.all():
        if _digits_only(other.mobile) == mobile:
            if _user_has_role(db, other.id, school_id, GUARDIAN_ROLE):
                raise AcademicError(
                    409,
                    f"{_user_name(other)} is already registered with this email or phone number. "
                    "Choose them as an existing parent instead.",
                )
            raise AcademicError(
                409,
                f"Mobile is already used by {_user_name(other)}. Link students on their record instead.",
            )


def _clear_primary_flags(db: Session, student_id: int) -> None:
    (
        db.query(StudentGuardian)
        .filter(
            StudentGuardian.student_id == student_id,
            StudentGuardian.deleted_at.is_(None),
            StudentGuardian.is_primary == 1,
        )
        .update({StudentGuardian.is_primary: 0, StudentGuardian.updated_at: _now()}, synchronize_session=False)
    )


def _link_guardian_row(
    db: Session,
    school_id: int,
    student: Student,
    parent: User,
    relationship: str,
    *,
    make_primary: bool | None,
) -> StudentGuardian:
    links = _active_guardian_links(db, student.id)
    for link in links:
        if link.guardian_user_id == parent.id:
            raise AcademicError(409, "Parent is already linked to this student")
    if len(links) >= MAX_GUARDIANS:
        raise AcademicError(409, "Student already has the maximum of 4 guardians")

    is_first = len(links) == 0
    primary = True if is_first else bool(make_primary)
    if primary and not is_first:
        _clear_primary_flags(db, student.id)

    row = StudentGuardian(
        school_id=school_id,
        student_id=student.id,
        guardian_user_id=parent.id,
        relationship_type=relationship,
        is_primary=1 if primary or is_first else 0,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.flush()
    _sync_legacy_guardian_id(db, student)
    if not _user_has_role(db, parent.id, school_id, GUARDIAN_ROLE):
        role = _ensure_school_role(db, school_id, GUARDIAN_ROLE)
        _assign_user_role(db, parent.id, role)
    return row


def list_students(
    db: Session,
    school_id: int,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
    session_year_id: int | None = None,
    class_id: int | None = None,
    class_section_id: int | None = None,
    parent_id: int | None = None,
    sort: str = "name",
    order: str = "asc",
) -> dict:
    page, page_size = _page(page, page_size)
    sort_key = (sort or "name").strip().lower()
    if sort_key not in SORT_FIELDS:
        raise AcademicError(422, "sort must be name, admission_no, admission_date or class")
    order_key = (order or "asc").strip().lower()
    if order_key not in {"asc", "desc"}:
        raise AcademicError(422, "order must be asc or desc")

    query = (
        db.query(Student, User)
        .join(User, User.id == Student.user_id)
        .outerjoin(
            ClassSection,
            (ClassSection.id == Student.class_section_id)
            & (ClassSection.school_id == school_id)
            & (ClassSection.deleted_at.is_(None)),
        )
        .outerjoin(
            SchoolClass,
            (SchoolClass.id == ClassSection.class_id)
            & (SchoolClass.school_id == school_id)
            & (SchoolClass.deleted_at.is_(None)),
        )
        .outerjoin(
            Section,
            (Section.id == ClassSection.section_id)
            & (Section.school_id == school_id)
            & (Section.deleted_at.is_(None)),
        )
        .filter(
            Student.school_id == school_id,
            Student.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
    )
    if status is not None:
        query = query.filter(User.status == int(status))
    if session_year_id is not None:
        query = query.filter(Student.session_year_id == int(session_year_id))
    if class_section_id is not None:
        query = query.filter(Student.class_section_id == int(class_section_id))
    if class_id is not None:
        query = query.filter(ClassSection.class_id == int(class_id))
    if parent_id is not None:
        query = query.join(
            StudentGuardian,
            (StudentGuardian.student_id == Student.id)
            & (StudentGuardian.deleted_at.is_(None))
            & (StudentGuardian.guardian_user_id == int(parent_id)),
        )
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                Student.admission_no.ilike(like),
                func.concat(User.first_name, " ", User.last_name).ilike(like),
            )
        )

    total = query.count()
    if sort_key == "admission_no":
        primary = Student.admission_no
        secondary = Student.id
    elif sort_key == "admission_date":
        primary = Student.admission_date
        secondary = Student.id
    elif sort_key == "class":
        primary = SchoolClass.name
        secondary = Section.name
    else:
        primary = User.first_name
        secondary = User.last_name
    if order_key == "desc":
        rows = (
            query.order_by(primary.desc().nullslast(), secondary.desc().nullslast(), Student.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
    else:
        rows = (
            query.order_by(primary.asc().nullslast(), secondary.asc().nullslast(), Student.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
    items = [_student_list_row(db, school_id, student, user) for student, user in rows]
    return _envelope(items, total, page, page_size)


def get_student(db: Session, school_id: int, student_id: int) -> dict:
    student, user = _owned_student(db, school_id, student_id)
    return _student_profile(db, school_id, student, user)


def _resolve_guardian_for_create(db: Session, school_id: int, guardian: dict) -> tuple[User, str]:
    if not isinstance(guardian, dict):
        raise AcademicError(422, "guardian is required")
    relationship = _normalize_relationship(guardian.get("relationship"))
    if guardian.get("parent_id") is not None:
        parent_id = int(guardian["parent_id"])
        parent = db.get(User, parent_id)
        if parent is None or parent.school_id != school_id or parent.deleted_at is not None:
            raise AcademicError(422, "guardian.parent_id does not belong to this school")
        return parent, relationship

    first_name = _require_str(guardian, "first_name", max_len=128)
    last_name = _require_str(guardian, "last_name", max_len=128)
    email = _normalize_email(guardian.get("email"), required=True)
    mobile = _normalize_mobile(guardian.get("mobile"), required=True)
    assert email is not None and mobile is not None
    _assert_parent_contact_unique(db, school_id, email=email, mobile=mobile)
    parent = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        mobile=mobile,
        password=hash_password(secrets.token_urlsafe(18)),
        status=1,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(parent)
    db.flush()
    role = _ensure_school_role(db, school_id, GUARDIAN_ROLE)
    _assign_user_role(db, parent.id, role)
    return parent, relationship


def create_student(db: Session, school_id: int, body: dict) -> dict:
    first_name = _require_str(body, "first_name", max_len=128)
    last_name = _require_str(body, "last_name", max_len=128)
    dob = _parse_date(body.get("dob"), "dob")
    _validate_dob(dob)
    gender = _normalize_gender(body.get("gender"), required=True)
    admission_date = _parse_date(body.get("admission_date"), "admission_date")
    if admission_date <= dob:
        raise AcademicError(422, "admission_date must be after dob")
    session_year_id = int(body.get("session_year_id") or 0)
    class_section_id = int(body.get("class_section_id") or 0)
    if not session_year_id:
        raise AcademicError(422, "session_year_id is required")
    if not class_section_id:
        raise AcademicError(422, "class_section_id is required")
    _assert_active_class_section(db, school_id, class_section_id, session_year_id)

    raw_adm = body.get("admission_no")
    if raw_adm is None or not str(raw_adm).strip():
        admission_no = _generate_admission_no(db, school_id, admission_date)
    else:
        admission_no = str(raw_adm).strip()
        if not ADMISSION_NO_RE.match(admission_no):
            raise AcademicError(
                422,
                "admission_no may only contain letters, digits, - and / (max 32 characters)",
            )
        _assert_admission_no_unique(db, school_id, admission_no)

    roll_number = body.get("roll_number")
    if roll_number is not None and roll_number != "":
        try:
            roll_number = int(roll_number)
        except (TypeError, ValueError) as exc:
            raise AcademicError(422, "roll_number must be between 1 and 9999") from exc
        if roll_number < 1 or roll_number > 9999:
            raise AcademicError(422, "roll_number must be between 1 and 9999")
    else:
        roll_number = None
    _assert_roll_unique(db, school_id, session_year_id, class_section_id, roll_number)

    email = _normalize_email(body.get("email"), required=False)
    mobile = _normalize_mobile(body.get("mobile"), required=False)
    current_address = _require_str(body, "current_address", max_len=512)
    permanent_address = _opt_str(body, "permanent_address", max_len=512)
    status = int(body.get("status") if body.get("status") is not None else 1)
    if status not in (0, 1):
        raise AcademicError(422, "status must be 0 or 1")

    if email:
        conflict = (
            db.query(User)
            .filter(
                User.school_id == school_id,
                func.lower(User.email) == email,
                User.deleted_at.is_(None),
            )
            .first()
        )
        if conflict is not None:
            raise AcademicError(409, "A student email already used in the school")
        stored_email = email
    else:
        # users.email is NOT NULL + unique(school_id, email). Store a private
        # placeholder; People API responses expose email as null via
        # _public_student_email.
        stored_email = _placeholder_student_email(school_id)

    guardian_body = body.get("guardian")
    parent, relationship = _resolve_guardian_for_create(db, school_id, guardian_body or {})

    user = User(
        first_name=first_name,
        last_name=last_name,
        email=stored_email,
        mobile=mobile,
        gender=gender,
        dob=dob,
        current_address=current_address,
        permanent_address=permanent_address,
        password=hash_password(secrets.token_urlsafe(18)),
        status=status,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(user)
    db.flush()

    student = Student(
        user_id=user.id,
        class_section_id=class_section_id,
        admission_no=admission_no,
        roll_number=roll_number,
        admission_date=admission_date,
        school_id=school_id,
        guardian_id=parent.id,
        session_year_id=session_year_id,
        enrollment_status="active" if status == 1 else "inactive",
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(student)
    db.flush()
    _link_guardian_row(
        db, school_id, student, parent, relationship, make_primary=True
    )
    _commit(db)
    db.refresh(student)
    db.refresh(user)
    return _student_profile(db, school_id, student, user)


def update_student(db: Session, school_id: int, student_id: int, body: dict) -> dict:
    student, user = _owned_student(db, school_id, student_id)
    if "guardian" in body:
        raise AcademicError(422, "Use guardian link endpoints to change guardians")

    admission_no = _require_str(body, "admission_no", max_len=32)
    if not ADMISSION_NO_RE.match(admission_no):
        raise AcademicError(
            422,
            "admission_no may only contain letters, digits, - and / (max 32 characters)",
        )
    _assert_admission_no_unique(db, school_id, admission_no, exclude_student_id=student.id)

    first_name = _require_str(body, "first_name", max_len=128)
    last_name = _require_str(body, "last_name", max_len=128)
    dob = _parse_date(body.get("dob"), "dob")
    _validate_dob(dob)
    gender = _normalize_gender(body.get("gender"), required=True)
    admission_date = _parse_date(body.get("admission_date"), "admission_date")
    if admission_date <= dob:
        raise AcademicError(422, "admission_date must be after dob")

    session_year_id = int(body.get("session_year_id") or student.session_year_id)
    class_section_id = int(body.get("class_section_id") or student.class_section_id)
    placement_changed = (
        class_section_id != student.class_section_id
        or session_year_id != student.session_year_id
    )
    if placement_changed:
        _assert_active_class_section(db, school_id, class_section_id, session_year_id)
    else:
        _same_school(db, SessionYear, session_year_id, school_id, "session_year_id")
        # Allow saving without re-validating soft-deleted class/section.

    roll_number = body.get("roll_number")
    if roll_number is not None and roll_number != "":
        try:
            roll_number = int(roll_number)
        except (TypeError, ValueError) as exc:
            raise AcademicError(422, "roll_number must be between 1 and 9999") from exc
        if roll_number < 1 or roll_number > 9999:
            raise AcademicError(422, "roll_number must be between 1 and 9999")
    else:
        roll_number = None
    _assert_roll_unique(
        db,
        school_id,
        session_year_id,
        class_section_id,
        roll_number,
        exclude_student_id=student.id,
    )

    email = _normalize_email(body.get("email"), required=False)
    mobile = _normalize_mobile(body.get("mobile"), required=False)
    current_address = _require_str(body, "current_address", max_len=512)
    permanent_address = _opt_str(body, "permanent_address", max_len=512)
    if "status" in body and body.get("status") is not None:
        status = int(body["status"])
        if status not in (0, 1):
            raise AcademicError(422, "status must be 0 or 1")
        user.status = status
        student.enrollment_status = "active" if status == 1 else "inactive"
        if status == 0:
            revoke_legacy_user_tokens(db, user.id)

    if "email" in body:
        if email:
            if email != (user.email or "").lower():
                _assert_unique_school_email(db, school_id, email)
                user.email = email
        else:
            # Cleared / omitted value — keep DB NOT NULL via placeholder; API returns null.
            if not _is_internal_student_email(user.email):
                user.email = _placeholder_student_email(school_id)

    user.first_name = first_name
    user.last_name = last_name
    user.dob = dob
    user.gender = gender
    user.mobile = mobile
    user.current_address = current_address
    user.permanent_address = permanent_address
    user.updated_at = _now()

    student.admission_no = admission_no
    student.admission_date = admission_date
    student.session_year_id = session_year_id
    student.class_section_id = class_section_id
    student.roll_number = roll_number
    student.updated_at = _now()
    _commit(db)
    db.refresh(student)
    db.refresh(user)
    return _student_profile(db, school_id, student, user)


def update_student_status(db: Session, school_id: int, student_id: int, status: int) -> dict:
    if status not in (0, 1):
        raise AcademicError(422, "status must be 0 or 1")
    student, user = _owned_student(db, school_id, student_id)
    user.status = status
    user.updated_at = _now()
    student.enrollment_status = "active" if status == 1 else "inactive"
    student.updated_at = _now()
    if status == 0:
        revoke_legacy_user_tokens(db, user.id)
    _commit(db)
    db.refresh(student)
    db.refresh(user)
    return _student_profile(db, school_id, student, user)


def link_guardian(
    db: Session, school_id: int, student_id: int, body: dict
) -> dict:
    student, user = _owned_student(db, school_id, student_id)
    parent_id = int(body.get("parent_id") or 0)
    if not parent_id:
        raise AcademicError(422, "parent_id is required")
    parent = db.get(User, parent_id)
    if parent is None or parent.school_id != school_id or parent.deleted_at is not None:
        raise AcademicError(422, "parent_id does not belong to this school")
    relationship = _normalize_relationship(body.get("relationship"))
    make_primary = body.get("is_primary")
    if make_primary is not None:
        make_primary = bool(make_primary)
    _link_guardian_row(
        db, school_id, student, parent, relationship, make_primary=make_primary
    )
    student.updated_at = _now()
    _commit(db)
    db.refresh(student)
    db.refresh(user)
    return _student_profile(db, school_id, student, user)


def unlink_guardian(
    db: Session, school_id: int, student_id: int, parent_id: int
) -> dict:
    student, user = _owned_student(db, school_id, student_id)
    links = _active_guardian_links(db, student.id)
    target = next((link for link in links if link.guardian_user_id == int(parent_id)), None)
    if target is None:
        raise AcademicError(404, "Record not found")
    if len(links) <= 1:
        raise AcademicError(
            409,
            f"{_user_name(user)} must keep at least one parent or guardian. Link another one first.",
        )
    was_primary = bool(target.is_primary)
    target.deleted_at = _now()
    target.updated_at = _now()
    target.is_primary = 0
    if was_primary:
        remaining = [link for link in links if link.id != target.id]
        if remaining:
            remaining[0].is_primary = 1
            remaining[0].updated_at = _now()
    _sync_legacy_guardian_id(db, student)
    student.updated_at = _now()
    _commit(db)
    db.refresh(student)
    db.refresh(user)
    return _student_profile(db, school_id, student, user)


def _parent_children(db: Session, school_id: int, parent_id: int) -> list[dict]:
    rows = (
        db.query(StudentGuardian, Student, User)
        .join(Student, Student.id == StudentGuardian.student_id)
        .join(User, User.id == Student.user_id)
        .filter(
            StudentGuardian.school_id == school_id,
            StudentGuardian.guardian_user_id == parent_id,
            StudentGuardian.deleted_at.is_(None),
            Student.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
        .order_by(Student.id.asc())
        .all()
    )
    items = []
    for link, student, user in rows:
        _class_id, class_name, section_name = _class_section_names(
            db, school_id, student.class_section_id
        )
        items.append(
            {
                "student_id": student.id,
                "name": _user_name(user),
                "admission_no": student.admission_no,
                "class_name": class_name,
                "section_name": section_name,
                "relationship": link.relationship_type,
                "is_primary": bool(link.is_primary),
                "status": int(user.status or 0),
            }
        )
    return items


def _parent_profile(db: Session, school_id: int, parent: User) -> dict:
    return {
        "id": parent.id,
        "first_name": parent.first_name,
        "last_name": parent.last_name,
        "name": _user_name(parent),
        "email": parent.email,
        "mobile": parent.mobile,
        "current_address": parent.current_address,
        "occupation": parent.occupation,
        "status": int(parent.status or 0),
        "children": _parent_children(db, school_id, parent.id),
    }


def list_parents(
    db: Session,
    school_id: int,
    *,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    status: int | None = None,
    email: str | None = None,
    mobile: str | None = None,
) -> dict:
    page, page_size = _page(page, page_size)
    query = (
        db.query(User)
        .join(
            ModelHasRole,
            (ModelHasRole.model_id == User.id) & (ModelHasRole.model_type == USER_MODEL),
        )
        .join(Role, Role.id == ModelHasRole.role_id)
        .filter(
            User.school_id == school_id,
            User.deleted_at.is_(None),
            Role.name == GUARDIAN_ROLE,
            Role.school_id == school_id,
            Role.guard_name == "web",
        )
    )
    if status is not None:
        query = query.filter(User.status == int(status))
    if email is not None and str(email).strip():
        query = query.filter(func.lower(User.email) == str(email).strip().lower())
    if mobile is not None and str(mobile).strip():
        digits = _digits_only(str(mobile))
        # Compare digit-only in Python for portability; filter candidates by length.
        candidates = query.all()
        matched_ids = [u.id for u in candidates if _digits_only(u.mobile) == digits]
        total = len(matched_ids)
        page_ids = matched_ids[(page - 1) * page_size : page * page_size]
        rows = [db.get(User, i) for i in page_ids]
        items = [_parent_profile(db, school_id, u) for u in rows if u is not None]
        return _envelope(items, total, page, page_size)
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                User.first_name.ilike(like),
                User.last_name.ilike(like),
                User.email.ilike(like),
                User.mobile.ilike(like),
                func.concat(User.first_name, " ", User.last_name).ilike(like),
            )
        )
    total = query.count()
    rows = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_parent_profile(db, school_id, row) for row in rows], total, page, page_size)


def get_parent(db: Session, school_id: int, parent_id: int) -> dict:
    return _parent_profile(db, school_id, _owned_parent(db, school_id, parent_id))


def create_parent(db: Session, school_id: int, body: dict) -> dict:
    first_name = _require_str(body, "first_name", max_len=128)
    last_name = _require_str(body, "last_name", max_len=128)
    email = _normalize_email(body.get("email"), required=True)
    mobile = _normalize_mobile(body.get("mobile"), required=True)
    assert email is not None and mobile is not None
    _assert_parent_contact_unique(db, school_id, email=email, mobile=mobile)
    current_address = _opt_str(body, "current_address", max_len=512)
    occupation = _opt_str(body, "occupation", max_len=255)
    status = int(body.get("status") if body.get("status") is not None else 1)
    if status not in (0, 1):
        raise AcademicError(422, "status must be 0 or 1")

    students_payload = body.get("students") or []
    if not isinstance(students_payload, list):
        raise AcademicError(422, "students must be a list")
    seen_students: set[int] = set()
    normalized_links: list[tuple[Student, str]] = []
    for entry in students_payload:
        if not isinstance(entry, dict):
            raise AcademicError(422, "students entries must be objects")
        sid = int(entry.get("student_id") or 0)
        if not sid:
            raise AcademicError(422, "students[].student_id is required")
        if sid in seen_students:
            raise AcademicError(422, "students[] must not contain duplicate student_id")
        seen_students.add(sid)
        student = _same_school(db, Student, sid, school_id, "students[].student_id")
        relationship = _normalize_relationship(entry.get("relationship"))
        if len(_active_guardian_links(db, student.id)) >= MAX_GUARDIANS:
            raise AcademicError(409, f"Student {sid} already has the maximum of 4 guardians")
        normalized_links.append((student, relationship))

    parent = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        mobile=mobile,
        current_address=current_address,
        occupation=occupation,
        password=hash_password(secrets.token_urlsafe(18)),
        status=status,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(parent)
    db.flush()
    role = _ensure_school_role(db, school_id, GUARDIAN_ROLE)
    _assign_user_role(db, parent.id, role)
    for student, relationship in normalized_links:
        _link_guardian_row(
            db, school_id, student, parent, relationship, make_primary=None
        )
        student.updated_at = _now()
    _commit(db)
    db.refresh(parent)
    return _parent_profile(db, school_id, parent)


def update_parent(db: Session, school_id: int, parent_id: int, body: dict) -> dict:
    parent = _owned_parent(db, school_id, parent_id)
    if "students" in body:
        raise AcademicError(422, "Use guardian link endpoints to change children")
    first_name = _require_str(body, "first_name", max_len=128)
    last_name = _require_str(body, "last_name", max_len=128)
    email = _normalize_email(body.get("email"), required=True)
    mobile = _normalize_mobile(body.get("mobile"), required=True)
    assert email is not None and mobile is not None
    _assert_parent_contact_unique(
        db, school_id, email=email, mobile=mobile, exclude_user_id=parent.id
    )
    parent.first_name = first_name
    parent.last_name = last_name
    parent.email = email
    parent.mobile = mobile
    if "current_address" in body:
        parent.current_address = _opt_str(body, "current_address", max_len=512)
    if "occupation" in body:
        parent.occupation = _opt_str(body, "occupation", max_len=255)
    if "status" in body and body.get("status") is not None:
        status = int(body["status"])
        if status not in (0, 1):
            raise AcademicError(422, "status must be 0 or 1")
        parent.status = status
        if status == 0:
            revoke_legacy_user_tokens(db, parent.id)
    parent.updated_at = _now()
    _commit(db)
    db.refresh(parent)
    return _parent_profile(db, school_id, parent)


def update_parent_status(db: Session, school_id: int, parent_id: int, status: int) -> dict:
    if status not in (0, 1):
        raise AcademicError(422, "status must be 0 or 1")
    parent = _owned_parent(db, school_id, parent_id)
    parent.status = status
    parent.updated_at = _now()
    if status == 0:
        revoke_legacy_user_tokens(db, parent.id)
    _commit(db)
    db.refresh(parent)
    return _parent_profile(db, school_id, parent)


def resolve_student_owner_user_id(db: Session, school_id: int, student_id: int) -> int:
    """Map people-API student id → legacy users.id for document ownership."""
    student, user = _owned_student(db, school_id, student_id)
    return user.id
