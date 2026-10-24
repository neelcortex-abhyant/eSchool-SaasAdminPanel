"""School-admin non-teaching Staff management and unified people listing.

Spatie roles
------------
- Non-teaching create assigns school-scoped ``Staff`` only (never ``Teacher``).
- ``mobile_auth.is_staff`` treats ``Staff`` as staff-app eligible.
- Legacy ``staffs`` rows without ``Staff`` or ``Teacher`` are excluded from
  role-specific lists until a reviewed backfill (not performed here).

Status mapping matches teachers: ``User.status`` = login gate;
``Staff.employment_status`` = business state only.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.tables import USER_MODEL, ModelHasRole, Role, Staff, User
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
)
from app.services.v1.school_teachers import (
    PASSWORD_MIN_LEN,
    TEACHER_ROLE_NAME,
    _assert_unique_employee_id,
    _normalize_employee_id,
    _normalize_employment_status,
    _normalize_org_label,
    _staff_for_user,
    _user_has_teacher_role,
)

STAFF_ROLE_NAME = "Staff"
PEOPLE_ROLE_FILTERS = frozenset({"all", "staff", "teacher"})


def _user_has_staff_role(db: Session, user_id: int, school_id: int) -> bool:
    row = db.execute(
        select(ModelHasRole.role_id)
        .join(Role, Role.id == ModelHasRole.role_id)
        .where(
            ModelHasRole.model_id == user_id,
            ModelHasRole.model_type == USER_MODEL,
            Role.name == STAFF_ROLE_NAME,
            Role.school_id == school_id,
            Role.guard_name == "web",
        )
        .limit(1)
    ).first()
    return row is not None


def _owned_non_teaching_staff(db: Session, school_id: int, user_id: int) -> tuple[User, Staff]:
    """Same-school User with Staff role, Staff row, and no Teacher role."""
    user = db.get(User, user_id)
    if (
        user is None
        or user.school_id != school_id
        or user.deleted_at is not None
        or not _user_has_staff_role(db, user.id, school_id)
        or _user_has_teacher_role(db, user.id, school_id)
    ):
        raise AcademicError(404, "Staff not found")
    staff = _staff_for_user(db, school_id, user.id)
    if staff is None:
        raise AcademicError(404, "Staff not found")
    return user, staff


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


def _opt_str(raw, max_len: int | None = None) -> str | None:
    if raw is None:
        return None
    cleaned = str(raw).strip()
    if not cleaned:
        return None
    if max_len is not None and len(cleaned) > max_len:
        raise AcademicError(422, f"value must be at most {max_len} characters")
    return cleaned


def _require_password(body: dict) -> str:
    raw = body.get("password")
    if raw is None or not str(raw):
        raise AcademicError(422, "password is required")
    password = str(raw)
    if len(password) < PASSWORD_MIN_LEN:
        raise AcademicError(422, f"password must be at least {PASSWORD_MIN_LEN} characters")
    return password


def _staff_item(user: User, staff: Staff) -> dict:
    """Public non-teaching staff payload — never includes password or tokens."""
    return {
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
        "role": STAFF_ROLE_NAME,
        "qualification": staff.qualification,
        "salary": staff.salary,
        "employee_id": staff.employee_id,
        "employee_code": staff.employee_id,
        "joining_date": staff.joining_date.isoformat() if staff.joining_date else None,
        "employment_status": staff.employment_status,
        "employment_type": staff.employment_status,
        "department": staff.department,
        "designation": staff.designation,
    }


def _parse_employment_body(body: dict, *, school_id: int, db: Session) -> dict:
    from app.services.v1.school_teachers import _next_employee_code

    employee_id = _normalize_employee_id(body.get("employee_id") or body.get("employee_code"))
    if employee_id is None:
        employee_id = _next_employee_code(db, school_id, "STF")
    from app.services.v1.school_teachers import EMPLOYMENT_STATUSES

    # Prefer employment_status; accept employment_type only when it matches known statuses.
    raw_status = body.get("employment_status")
    if raw_status is None:
        alias = str(body.get("employment_type") or "").strip().lower()
        if alias in EMPLOYMENT_STATUSES:
            raw_status = alias
    joining_date = _parse_date(body.get("joining_date"), "joining_date")
    employment_status = _normalize_employment_status(raw_status)
    department = _normalize_org_label(body.get("department"), "department")
    designation = _normalize_org_label(body.get("designation"), "designation")
    qualification = _opt_str(body.get("qualification"), 512)
    salary = float(body.get("salary") or 0)
    if salary < 0:
        raise AcademicError(422, "salary must be >= 0")
    return {
        "employee_id": employee_id,
        "joining_date": joining_date,
        "employment_status": employment_status,
        "department": department,
        "designation": designation,
        "qualification": qualification,
        "salary": salary,
    }


def create_staff(db: Session, school_id: int, body: dict) -> dict:
    """Create User + Staff and assign school-scoped Staff role (not Teacher)."""
    for field in ("first_name", "last_name", "email"):
        if field not in body or not str(body.get(field) or "").strip():
            raise AcademicError(422, f"{field} is required")
    password = _require_password(body)
    email = str(body["email"]).strip().lower()
    _assert_unique_school_email(db, school_id, email)

    emp = _parse_employment_body(body, school_id=school_id, db=db)
    _assert_unique_employee_id(db, school_id, emp["employee_id"])

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
        qualification=emp["qualification"],
        salary=emp["salary"],
        employee_id=emp["employee_id"],
        joining_date=emp["joining_date"],
        employment_status=emp["employment_status"],
        department=emp["department"],
        designation=emp["designation"],
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(staff)

    role = _ensure_school_role(db, school_id, STAFF_ROLE_NAME)
    _assign_user_role(db, user.id, role)
    _commit(db)
    db.refresh(user)
    db.refresh(staff)
    return _staff_item(user, staff)


def _non_teaching_staff_query(db: Session, school_id: int):
    """Users with Staff role + Staff row, excluding anyone who also holds Teacher."""
    teacher_user_ids = (
        select(ModelHasRole.model_id)
        .join(Role, Role.id == ModelHasRole.role_id)
        .where(
            ModelHasRole.model_type == USER_MODEL,
            Role.name == TEACHER_ROLE_NAME,
            Role.school_id == school_id,
            Role.guard_name == "web",
        )
    )
    return (
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
            Role.name == STAFF_ROLE_NAME,
            Role.school_id == school_id,
            Role.guard_name == "web",
            ~User.id.in_(teacher_user_ids),
        )
    )


def _apply_filters(query, *, q, status, employment_status, department, designation):
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
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
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
    return query


def list_staff(
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
    role: str | None = None,
) -> dict:
    """Paginated non-teaching staff (Spatie Staff, not Teacher)."""
    if role is not None and str(role).strip() and str(role).strip().lower() not in ("staff",):
        raise AcademicError(422, "role filter on /staff must be Staff only")
    page, page_size = _page(page, page_size)
    query = _non_teaching_staff_query(db, school_id)
    query = _apply_filters(
        query,
        q=q,
        status=status,
        employment_status=employment_status,
        department=department,
        designation=designation,
    )
    total = query.count()
    rows = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return _envelope([_staff_item(user, staff) for user, staff in rows], total, page, page_size)


def get_staff(db: Session, school_id: int, staff_user_id: int) -> dict:
    user, staff = _owned_non_teaching_staff(db, school_id, staff_user_id)
    return _staff_item(user, staff)


def list_departments(db: Session, school_id: int) -> dict:
    query = (
        db.query(Staff.department)
        .join(User, User.id == Staff.user_id)
        .join(
            ModelHasRole,
            (ModelHasRole.model_id == User.id) & (ModelHasRole.model_type == USER_MODEL),
        )
        .join(Role, Role.id == ModelHasRole.role_id)
        .filter(
            Staff.school_id == school_id,
            Staff.department.isnot(None),
            Staff.department != "",
            Role.name == STAFF_ROLE_NAME,
            Role.school_id == school_id,
            Role.guard_name == "web",
            User.deleted_at.is_(None),
        )
    )
    values = sorted({(row[0] or "").strip() for row in query.all() if row[0] and str(row[0]).strip()})
    return {"items": values}


def update_staff(db: Session, school_id: int, staff_user_id: int, body: dict) -> dict:
    user, staff = _owned_non_teaching_staff(db, school_id, staff_user_id)
    if "status" in body:
        raise AcademicError(422, "Use PATCH /staff/{id}/status to change account status")
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
    if "employee_id" in body or "employee_code" in body:
        employee_id = _normalize_employee_id(body.get("employee_id") or body.get("employee_code"))
        _assert_unique_employee_id(db, school_id, employee_id, exclude_staff_id=staff.id)
        staff.employee_id = employee_id
    if "joining_date" in body:
        staff.joining_date = _parse_date(body.get("joining_date"), "joining_date")
    if "employment_status" in body or "employment_type" in body:
        raw = body.get("employment_status")
        if raw is None:
            raw = body.get("employment_type")
        staff.employment_status = _normalize_employment_status(raw)
    if "department" in body:
        staff.department = _normalize_org_label(body.get("department"), "department")
    if "designation" in body:
        staff.designation = _normalize_org_label(body.get("designation"), "designation")

    user.updated_at = _now()
    staff.updated_at = _now()
    _commit(db)
    db.refresh(user)
    db.refresh(staff)
    return _staff_item(user, staff)


def update_staff_status(db: Session, school_id: int, staff_user_id: int, status: int) -> dict:
    if status not in (0, 1):
        raise AcademicError(422, "status must be 0 or 1")
    user, staff = _owned_non_teaching_staff(db, school_id, staff_user_id)
    user.status = status
    user.updated_at = _now()
    if status == 0:
        revoke_legacy_user_tokens(db, user.id)
    _commit(db)
    return _staff_item(user, staff)


def list_people(
    db: Session,
    school_id: int,
    q: str = "",
    page: int = 1,
    page_size: int = 20,
    *,
    role: str = "all",
    status: int | None = None,
    employment_status: str | None = None,
    department: str | None = None,
    designation: str | None = None,
) -> dict:
    """Unified Teacher + non-teaching Staff listing for one school."""
    page, page_size = _page(page, page_size)
    role_key = (role or "all").strip().lower()
    if role_key not in PEOPLE_ROLE_FILTERS:
        raise AcademicError(422, "role must be one of: teacher, staff, all")

    from app.services.v1 import school_teachers as teachers_svc

    if role_key == "teacher":
        return teachers_svc.list_teachers(
            db,
            school_id,
            q,
            page,
            page_size,
            status=status,
            employment_status=employment_status,
            department=department,
            designation=designation,
        )
    if role_key == "staff":
        return list_staff(
            db,
            school_id,
            q,
            page,
            page_size,
            status=status,
            employment_status=employment_status,
            department=department,
            designation=designation,
        )

    # Merge teachers + non-teaching staff, then paginate in Python for a stable envelope.
    teachers = teachers_svc.list_teachers(
        db,
        school_id,
        q,
        page=1,
        page_size=10_000,
        status=status,
        employment_status=employment_status,
        department=department,
        designation=designation,
    )["items"]
    staff_rows = list_staff(
        db,
        school_id,
        q,
        page=1,
        page_size=10_000,
        status=status,
        employment_status=employment_status,
        department=department,
        designation=designation,
    )["items"]
    merged = sorted(teachers + staff_rows, key=lambda item: item["id"], reverse=True)
    total = len(merged)
    start = (page - 1) * page_size
    return _envelope(merged[start : start + page_size], total, page, page_size)
