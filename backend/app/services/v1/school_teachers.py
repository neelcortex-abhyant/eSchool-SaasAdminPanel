"""School-admin Teacher management: User + Staff + Spatie Teacher role.

Status mapping
--------------
- ``User.status`` (0|1): account/login gate. ``PATCH …/status`` updates this only.
- ``Staff.employment_status`` (active|on_leave|resigned|terminated): business
  employment state. Updated via profile create/PATCH only. Does **not** by
  itself block login; deactivate the account with ``User.status=0`` for that.

Teacher identity for clients and ``TeacherAssignment.teacher_user_id`` remains
``users.id``. Legacy Staff rows without the Teacher role are not listed or
profiled here and are not auto-promoted.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tables import USER_MODEL, ModelHasRole, Role, Staff, TeacherAssignment, User
from app.services.mobile_auth import revoke_legacy_user_tokens
from app.services.v1.school_academics import (
    AcademicError,
    _assert_unique_school_email,
    _assign_user_role,
    _commit,
    _ensure_school_role,
    _envelope,
    _now,
    _page,
    _user_name,
    list_teacher_assignments,
)
from app.services.v1.school_people import owner_documents

TEACHER_ROLE_NAME = "Teacher"
EMPLOYMENT_STATUSES = frozenset({"active", "on_leave", "resigned", "terminated"})
EMPLOYMENT_DEFAULT = "active"
PASSWORD_MIN_LEN = 8


def _user_has_teacher_role(db: Session, user_id: int, school_id: int) -> bool:
    row = db.execute(
        select(ModelHasRole.role_id)
        .join(Role, Role.id == ModelHasRole.role_id)
        .where(
            ModelHasRole.model_id == user_id,
            ModelHasRole.model_type == USER_MODEL,
            Role.name == TEACHER_ROLE_NAME,
            Role.school_id == school_id,
            Role.guard_name == "web",
        )
        .limit(1)
    ).first()
    return row is not None


def _staff_for_user(db: Session, school_id: int, user_id: int) -> Staff | None:
    return db.query(Staff).filter(Staff.user_id == user_id, Staff.school_id == school_id).first()


def _owned_teacher(db: Session, school_id: int, teacher_id: int) -> tuple[User, Staff]:
    """Same-school User with Teacher role and Staff row, or 404."""
    user = db.get(User, teacher_id)
    if (
        user is None
        or user.school_id != school_id
        or user.deleted_at is not None
        or not _user_has_teacher_role(db, user.id, school_id)
    ):
        raise AcademicError(404, "Teacher not found")
    staff = _staff_for_user(db, school_id, user.id)
    if staff is None:
        raise AcademicError(404, "Teacher not found")
    return user, staff


def _normalize_employment_status(raw) -> str:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return EMPLOYMENT_DEFAULT
    value = str(raw).strip().lower()
    if value not in EMPLOYMENT_STATUSES:
        raise AcademicError(
            422,
            "employment_status must be one of: active, on_leave, resigned, terminated",
        )
    return value


def _normalize_employee_id(raw) -> str | None:
    if raw is None:
        return None
    cleaned = str(raw).strip()
    return cleaned or None


def _normalize_org_label(raw, field: str) -> str | None:
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if len(cleaned) > 128:
        raise AcademicError(422, f"{field} must be at most 128 characters")
    return cleaned or None


def _assert_unique_employee_id(
    db: Session,
    school_id: int,
    employee_id: str | None,
    *,
    exclude_staff_id: int | None = None,
) -> None:
    if employee_id is None:
        return
    query = db.query(Staff).filter(Staff.school_id == school_id, Staff.employee_id == employee_id)
    if exclude_staff_id is not None:
        query = query.filter(Staff.id != exclude_staff_id)
    if query.first() is not None:
        raise AcademicError(409, "employee_id already exists in this school")


def _parse_date(raw, field: str = "date") -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    text = str(raw).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise AcademicError(422, f"{field} must be a valid ISO date (YYYY-MM-DD)") from exc


def _require_password(body: dict) -> str:
    raw = body.get("password")
    if raw is None or not str(raw):
        raise AcademicError(422, "password is required")
    password = str(raw)
    if len(password) < PASSWORD_MIN_LEN:
        raise AcademicError(422, f"password must be at least {PASSWORD_MIN_LEN} characters")
    return password


def _assignment_count(db: Session, school_id: int, teacher_user_id: int) -> int:
    return (
        db.query(TeacherAssignment)
        .filter(
            TeacherAssignment.school_id == school_id,
            TeacherAssignment.teacher_user_id == teacher_user_id,
            TeacherAssignment.deleted_at.is_(None),
        )
        .count()
    )


def _opt_str(raw, max_len: int | None = None) -> str | None:
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return None
    if max_len is not None and len(cleaned) > max_len:
        raise AcademicError(422, f"value must be at most {max_len} characters")
    return cleaned


def _teacher_item(user: User, staff: Staff, *, assignment_count: int | None = None) -> dict:
    """Public teacher payload — never includes password or tokens."""
    item = {
        "id": user.id,
        "staff_id": staff.id,
        "name": _user_name(user),
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "mobile": user.mobile,
        "gender": user.gender,
        "dob": user.dob.isoformat() if user.dob else None,
        "current_address": user.current_address,
        "permanent_address": user.permanent_address,
        "country_code": user.country_code,
        "image": user.image,
        "photo_url": user.image,
        "status": user.status,
        "role": TEACHER_ROLE_NAME,
        "qualification": staff.qualification,
        "salary": staff.salary,
        "employee_id": staff.employee_id,
        "employee_code": staff.employee_id,
        "joining_date": staff.joining_date.isoformat() if staff.joining_date else None,
        "employment_status": staff.employment_status,
        # People-contract alias; employment_type enum is not stored — status is the live field.
        "employment_type": staff.employment_status,
        "department": staff.department,
        "designation": staff.designation,
    }
    if assignment_count is not None:
        item["assignment_count"] = assignment_count
    return item


def _next_employee_code(db: Session, school_id: int, prefix: str) -> str:
    like = f"{prefix}%"
    rows = (
        db.query(Staff.employee_id)
        .filter(
            Staff.school_id == school_id,
            Staff.employee_id.isnot(None),
            Staff.employee_id.ilike(like),
        )
        .with_for_update()
        .all()
    )
    max_seq = 0
    for (code,) in rows:
        suffix = str(code)[len(prefix) :]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:04d}"


def list_departments(db: Session, school_id: int, *, teachers_only: bool) -> dict:
    query = db.query(Staff.department).filter(
        Staff.school_id == school_id,
        Staff.department.isnot(None),
        Staff.department != "",
    )
    if teachers_only:
        query = (
            query.join(User, User.id == Staff.user_id)
            .join(
                ModelHasRole,
                (ModelHasRole.model_id == User.id) & (ModelHasRole.model_type == USER_MODEL),
            )
            .join(Role, Role.id == ModelHasRole.role_id)
            .filter(
                Role.name == TEACHER_ROLE_NAME,
                Role.school_id == school_id,
                Role.guard_name == "web",
                User.deleted_at.is_(None),
            )
        )
    values = sorted({(row[0] or "").strip() for row in query.all() if row[0] and str(row[0]).strip()})
    return {"items": values}


def _apply_employment_filters(query, *, status, employment_status, department, designation):
    if status is not None:
        query = query.filter(User.status == int(status))
    if employment_status is not None and str(employment_status).strip():
        query = query.filter(
            Staff.employment_status == _normalize_employment_status(employment_status)
        )
    if department is not None and str(department).strip():
        query = query.filter(Staff.department.ilike(str(department).strip()))
    if designation is not None and str(designation).strip():
        query = query.filter(Staff.designation.ilike(str(designation).strip()))
    return query


def _apply_search(query, q: str):
    if not q or not q.strip():
        return query
    like = f"%{q.strip()}%"
    return query.filter(
        or_(
            User.first_name.ilike(like),
            User.last_name.ilike(like),
            User.email.ilike(like),
            User.mobile.ilike(like),
            Staff.employee_id.ilike(like),
            Staff.department.ilike(like),
            Staff.designation.ilike(like),
        )
    )


def create_teacher(db: Session, school_id: int, body: dict) -> dict:
    """Create User + Staff and assign school-scoped Teacher role.

    Password is required and hashed (never returned). Account is active
    (``User.status=1``). Default ``employment_status`` is ``active``.
    """
    for field in ("first_name", "last_name", "email"):
        if field not in body or not str(body.get(field) or "").strip():
            raise AcademicError(422, f"{field} is required")
    password = _require_password(body)
    email = str(body["email"]).strip().lower()
    _assert_unique_school_email(db, school_id, email)

    # Accept people-contract alias employee_code.
    employee_id = _normalize_employee_id(body.get("employee_id") or body.get("employee_code"))
    if employee_id is None:
        employee_id = _next_employee_code(db, school_id, "TCH")
    _assert_unique_employee_id(db, school_id, employee_id)
    raw_status = body.get("employment_status")
    if raw_status is None:
        alias = str(body.get("employment_type") or "").strip().lower()
        if alias in EMPLOYMENT_STATUSES:
            raw_status = alias
    employment_status = _normalize_employment_status(raw_status)
    joining_date = _parse_date(body.get("joining_date"), "joining_date")
    department = _normalize_org_label(body.get("department"), "department")
    designation = _normalize_org_label(body.get("designation"), "designation")
    qualification = _opt_str(body.get("qualification"), 512)
    salary = float(body.get("salary") or 0)
    if salary < 0:
        raise AcademicError(422, "salary must be >= 0")

    user = User(
        first_name=str(body["first_name"]).strip(),
        last_name=str(body["last_name"]).strip(),
        email=email,
        mobile=_opt_str(body.get("mobile"), 255),
        gender=_opt_str(body.get("gender"), 16),
        dob=_parse_date(body.get("dob"), "dob"),
        current_address=_opt_str(body.get("current_address"), 512),
        permanent_address=_opt_str(body.get("permanent_address"), 512),
        country_code=_opt_str(body.get("country_code"), 32),
        image=_opt_str(body.get("image"), 512),
        password=hash_password(password),
        status=1,
        school_id=school_id,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(user)
    db.flush()

    staff = Staff(
        user_id=user.id,
        school_id=school_id,
        qualification=qualification,
        salary=salary,
        employee_id=employee_id,
        joining_date=joining_date,
        employment_status=employment_status,
        department=department,
        designation=designation,
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(staff)

    role = _ensure_school_role(db, school_id, TEACHER_ROLE_NAME)
    _assign_user_role(db, user.id, role)
    _commit(db)
    db.refresh(user)
    db.refresh(staff)
    return _teacher_item(user, staff, assignment_count=0)


def list_teachers(
    db: Session,
    school_id: int,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    *,
    status: int | None = None,
    employment_status: str | None = None,
    department: str | None = None,
    designation: str | None = None,
) -> dict:
    """Paginated teachers: User with school Teacher role and Staff row."""
    page, page_size = _page(page, page_size)
    query = (
        db.query(User, Staff)
        .join(Staff, (Staff.user_id == User.id) & (Staff.school_id == school_id))
        .join(
            ModelHasRole,
            (ModelHasRole.model_id == User.id) & (ModelHasRole.model_type == USER_MODEL),
        )
        .join(Role, Role.id == ModelHasRole.role_id)
        .filter(
            User.school_id == school_id,
            User.deleted_at.is_(None),
            Role.name == TEACHER_ROLE_NAME,
            Role.school_id == school_id,
            Role.guard_name == "web",
        )
    )
    query = _apply_employment_filters(
        query,
        status=status,
        employment_status=employment_status,
        department=department,
        designation=designation,
    )
    query = _apply_search(query, q)
    total = query.count()
    rows = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = [
        _teacher_item(
            user,
            staff,
            assignment_count=_assignment_count(db, school_id, user.id),
        )
        for user, staff in rows
    ]
    return _envelope(items, total, page, page_size)


def get_teacher(db: Session, school_id: int, teacher_id: int) -> dict:
    user, staff = _owned_teacher(db, school_id, teacher_id)
    item = _teacher_item(
        user, staff, assignment_count=_assignment_count(db, school_id, user.id)
    )
    assignments = list_teacher_assignments(
        db, school_id, page=1, page_size=50, teacher_id=user.id
    )
    item["assignments"] = assignments["items"]
    item["documents"] = owner_documents(
        db, school_id, owner_kind="teacher", route_owner_id=user.id, user_id=user.id
    )
    return item


def update_teacher(db: Session, school_id: int, teacher_id: int, body: dict) -> dict:
    """Partial profile / employment update. Does not change roles or passwords."""
    user, staff = _owned_teacher(db, school_id, teacher_id)
    if "status" in body:
        raise AcademicError(422, "Use PATCH /teachers/{id}/status to change account status")
    if "password" in body or "roles" in body or "role" in body:
        raise AcademicError(422, "password and roles cannot be changed on this endpoint")

    if "first_name" in body:
        cleaned = str(body["first_name"]).strip()
        if not cleaned:
            raise AcademicError(422, "first_name is required")
        user.first_name = cleaned
    if "last_name" in body:
        cleaned = str(body["last_name"]).strip()
        if not cleaned:
            raise AcademicError(422, "last_name is required")
        user.last_name = cleaned
    if "email" in body:
        email = str(body["email"]).strip().lower()
        if not email:
            raise AcademicError(422, "email is required")
        if email != (user.email or "").lower():
            _assert_unique_school_email(db, school_id, email)
        user.email = email
    if "mobile" in body:
        user.mobile = _opt_str(body.get("mobile"), 255)
    if "gender" in body:
        user.gender = _opt_str(body.get("gender"), 16)
    if "dob" in body:
        user.dob = _parse_date(body.get("dob"), "dob")
    if "current_address" in body:
        user.current_address = _opt_str(body.get("current_address"), 512)
    if "permanent_address" in body:
        user.permanent_address = _opt_str(body.get("permanent_address"), 512)
    if "country_code" in body:
        user.country_code = _opt_str(body.get("country_code"), 32)
    if "image" in body:
        user.image = _opt_str(body.get("image"), 512)

    if "qualification" in body:
        staff.qualification = _opt_str(body.get("qualification"), 512)
    if "salary" in body:
        salary = float(body["salary"] if body["salary"] is not None else 0)
        if salary < 0:
            raise AcademicError(422, "salary must be >= 0")
        staff.salary = salary
    if "employee_id" in body:
        employee_id = _normalize_employee_id(body.get("employee_id") or body.get("employee_code"))
        _assert_unique_employee_id(db, school_id, employee_id, exclude_staff_id=staff.id)
        staff.employee_id = employee_id
    if "joining_date" in body:
        staff.joining_date = _parse_date(body.get("joining_date"), "joining_date")
    if "employment_status" in body:
        staff.employment_status = _normalize_employment_status(body.get("employment_status"))
    if "department" in body:
        staff.department = _normalize_org_label(body.get("department"), "department")
    if "designation" in body:
        staff.designation = _normalize_org_label(body.get("designation"), "designation")

    user.updated_at = _now()
    staff.updated_at = _now()
    _commit(db)
    db.refresh(user)
    db.refresh(staff)
    return _teacher_item(
        user, staff, assignment_count=_assignment_count(db, school_id, user.id)
    )


def update_teacher_status(db: Session, school_id: int, teacher_id: int, status: int) -> dict:
    """Activate/deactivate account via ``User.status`` (0|1).

    Preserves User, Staff, and historical ``TeacherAssignment`` rows.
    Does not change Spatie roles or employment_status.
    """
    if status not in (0, 1):
        raise AcademicError(422, "status must be 0 or 1")
    user, staff = _owned_teacher(db, school_id, teacher_id)
    user.status = status
    user.updated_at = _now()
    if status == 0:
        revoke_legacy_user_tokens(db, user.id)
    _commit(db)
    return _teacher_item(
        user, staff, assignment_count=_assignment_count(db, school_id, user.id)
    )
