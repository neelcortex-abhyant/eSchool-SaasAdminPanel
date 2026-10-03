from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.responses import (
    INACTIVATED_USER,
    INVALID_LOGIN,
    VALIDATION_ERROR,
    fail,
    ok,
)
from app.core.security import hash_token, new_plain_token, utcnow, verify_password
from app.models.tables import (
    USER_MODEL,
    ClassSection,
    ModelHasRole,
    PersonalAccessToken,
    Role,
    School,
    SchoolClass,
    Section,
    SessionYear,
    Student,
    User,
)


def user_roles(db: Session, user_id: int) -> set[str]:
    rows = db.execute(
        select(Role.name)
        .join(ModelHasRole, ModelHasRole.role_id == Role.id)
        .where(ModelHasRole.model_id == user_id, ModelHasRole.model_type == USER_MODEL)
    ).all()
    return {row[0] for row in rows}


def find_school(central: Session, code: str) -> School | None:
    return central.scalar(select(School).where(School.code == code, School.deleted_at.is_(None)))


def issue_token(db: Session, user: User) -> str:
    plain = new_plain_token()
    row = PersonalAccessToken(
        tokenable_type=USER_MODEL,
        tokenable_id=user.id,
        name=user.first_name,
        token=hash_token(plain),
        abilities=json.dumps(["*"]),
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return f"{row.id}|{plain}"


def find_token_user(db: Session, bearer: str | None) -> User | None:
    if not bearer or "|" not in bearer:
        return None
    token_id, plain = bearer.split("|", 1)
    if not token_id.isdigit():
        return None
    row = db.get(PersonalAccessToken, int(token_id))
    if row is None or row.token != hash_token(plain):
        return None
    if row.expires_at and row.expires_at < utcnow():
        return None
    row.last_used_at = utcnow()
    db.commit()
    return db.get(User, row.tokenable_id)


def _dt(value) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _school_payload(school: School) -> dict:
    return {
        "id": school.id,
        "name": school.name,
        "address": school.address,
        "support_phone": school.support_phone,
        "support_email": school.support_email,
        "tagline": school.tagline,
        "logo": school.logo,
        "status": school.status,
        "code": school.code,
        "domain": school.domain,
    }


def _class_section_payload(db: Session, class_section_id: int) -> Optional[dict]:
    cs = db.get(ClassSection, class_section_id)
    if cs is None:
        return {"id": class_section_id}
    school_class = db.get(SchoolClass, cs.class_id)
    section = db.get(Section, cs.section_id)
    return {
        "id": cs.id,
        "class_id": cs.class_id,
        "section_id": cs.section_id,
        "medium_id": cs.medium_id,
        "school_id": cs.school_id,
        "class": None if school_class is None else {"id": school_class.id, "name": school_class.name},
        "section": None if section is None else {"id": section.id, "name": section.name},
    }


def _guardian_payload(db: Session, guardian_id: int) -> Optional[dict]:
    guardian = db.get(User, guardian_id)
    if guardian is None:
        return None
    return {
        "id": guardian.id,
        "first_name": guardian.first_name,
        "last_name": guardian.last_name,
        "email": guardian.email,
        "mobile": guardian.mobile,
        "image": guardian.image,
        "occupation": guardian.occupation,
    }


def student_user_resource(
    db: Session,
    user: User,
    student: Student,
    school: School,
    extra_data: Optional[dict] = None,
) -> dict:
    """Mirrors Laravel UserDataResource for Student role."""
    extra = extra_data or {}
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "country_code": user.country_code,
        "mobile": user.mobile,
        "roll_number": student.roll_number,
        "admission_no": student.admission_no,
        "admission_date": _dt(student.admission_date),
        "gender": user.gender,
        "image": user.image,
        "dob": _dt(user.dob),
        "current_address": user.current_address,
        "permanent_address": user.permanent_address,
        "occupation": user.occupation,
        "status": user.status,
        "fcm_id": extra.get("fcm_id"),
        "web_fcm": extra.get("web_fcm"),
        "device_type": extra.get("device_type"),
        "school_id": user.school_id,
        "session_year_id": student.session_year_id,
        "email_verified_at": _dt(user.email_verified_at),
        "created_at": _dt(user.created_at),
        "updated_at": _dt(user.updated_at),
        "class_section": _class_section_payload(db, student.class_section_id),
        "guardian": _guardian_payload(db, student.guardian_id),
        "school": _school_payload(school),
    }


def guardian_user_resource(
    db: Session,
    user: User,
    school: School,
    children: list[Student],
    extra_data: Optional[dict] = None,
) -> dict:
    """Mirrors Laravel UserDataResource for Guardian role with complete children."""
    extra = extra_data or {}
    child_payloads = []
    for child in children:
        child_user = db.get(User, child.user_id)
        if child_user is None:
            continue
        child_payloads.append(student_user_resource(db, child_user, child, school, extra_data={}))
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "country_code": user.country_code,
        "mobile": user.mobile,
        "gender": user.gender,
        "image": user.image,
        "dob": _dt(user.dob),
        "current_address": user.current_address,
        "permanent_address": user.permanent_address,
        "occupation": user.occupation,
        "status": user.status,
        "fcm_id": extra.get("fcm_id"),
        "web_fcm": extra.get("web_fcm"),
        "device_type": extra.get("device_type"),
        "email_verified_at": _dt(user.email_verified_at),
        "created_at": _dt(user.created_at),
        "updated_at": _dt(user.updated_at),
        "children": child_payloads,
        "school": _school_payload(school),
    }


def staff_user_resource(
    db: Session,
    user: User,
    school: School,
    extra_data: Optional[dict] = None,
) -> dict:
    """Staff/teacher/driver login graph (role-aware; salary nesting filled as data arrives)."""
    extra = extra_data or {}
    roles = sorted(user_roles(db, user.id))
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "country_code": user.country_code,
        "mobile": user.mobile,
        "gender": user.gender,
        "image": user.image,
        "dob": _dt(user.dob),
        "current_address": user.current_address,
        "permanent_address": user.permanent_address,
        "occupation": user.occupation,
        "status": user.status,
        "fcm_id": extra.get("fcm_id"),
        "web_fcm": extra.get("web_fcm"),
        "device_type": extra.get("device_type"),
        "school_id": user.school_id,
        "email_verified_at": _dt(user.email_verified_at),
        "created_at": _dt(user.created_at),
        "updated_at": _dt(user.updated_at),
        "roles": [{"name": name} for name in roles],
        "school": _school_payload(school),
        "teacher": None,
        "staff": None,
    }


def default_session_year(db: Session, school_id: int) -> SessionYear | None:
    return db.scalar(
        select(SessionYear).where(
            SessionYear.school_id == school_id,
            SessionYear.default == 1,
            SessionYear.deleted_at.is_(None),
        )
    )


def login_student(
    central: Session,
    school_db: Session,
    school: School,
    gr_number: str,
    password: str,
    fcm_id: str | None,
) -> dict:
    user = school_db.scalar(select(User).where(User.email == gr_number))
    student = (
        None
        if user is None
        else school_db.scalar(select(Student).where(Student.user_id == user.id, Student.deleted_at.is_(None)))
    )
    if user is None or student is None or not verify_password(password, user.password):
        return fail("Invalid Login Credentials", code=INVALID_LOGIN)
    if user.deleted_at is not None:
        return fail("your_account_has_been_deactivated_please_contact_admin", code=INACTIVATED_USER)
    session_year = default_session_year(school_db, school.id)
    if session_year is None or student.session_year_id != session_year.id or user.status != 1:
        return fail("Invalid Login Credentials", code=INVALID_LOGIN)
    if school.status == 0:
        return fail("Your account has been deactivated", code=INVALID_LOGIN)
    if fcm_id:
        user.fcm_id = fcm_id
        school_db.commit()
    token = issue_token(school_db, user)
    extra = {"fcm_id": fcm_id, "web_fcm": None, "device_type": None}
    data = student_user_resource(school_db, user, student, school, extra_data=extra)
    return ok("User logged-in!", data, token=token)


def login_parent(school_db: Session, school: School, email: str, password: str, fcm_id: str | None) -> dict:
    user = school_db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password) or user.deleted_at is not None:
        return fail("Invalid Login Credentials", code=INVALID_LOGIN)
    if "Guardian" not in user_roles(school_db, user.id):
        return fail("Invalid Login Credentials", code=INVALID_LOGIN)
    session_year = default_session_year(school_db, school.id)
    children = []
    if session_year is not None:
        children = list(
            school_db.scalars(
                select(Student).where(
                    Student.guardian_id == user.id,
                    Student.session_year_id == session_year.id,
                    Student.deleted_at.is_(None),
                )
            )
        )
    active = []
    for child in children:
        child_user = school_db.get(User, child.user_id)
        if child_user and child_user.status == 1 and child_user.deleted_at is None:
            active.append(child)
    if not active:
        return fail("You currently don't have any active children.", code=INVALID_LOGIN)
    if fcm_id:
        user.fcm_id = fcm_id
        school_db.commit()
    token = issue_token(school_db, user)
    extra = {"fcm_id": fcm_id, "web_fcm": None, "device_type": None}
    data = guardian_user_resource(school_db, user, school, active, extra_data=extra)
    return ok("User logged-in!", data, token=token)


def login_teacher(school_db: Session, school: School, email: str, password: str, fcm_id: str | None) -> dict:
    user = school_db.scalar(select(User).where(User.email == email))
    if user is None:
        return fail("Invalid Login Credentials", code=INVALID_LOGIN)
    roles = user_roles(school_db, user.id)
    if "School Admin" not in roles and roles.intersection({"Student", "Parent", "Guardian"}):
        return fail("You must have a teacher / Staff role to log in.", code=INVALID_LOGIN)
    if not verify_password(password, user.password):
        return fail("Invalid Login Credentials", code=INVALID_LOGIN)
    if user.deleted_at is not None or school.status == 0 or user.status == 0:
        return fail("your_account_has_been_deactivated_please_contact_admin", code=INACTIVATED_USER)
    if fcm_id:
        user.fcm_id = fcm_id
        school_db.commit()
    token = issue_token(school_db, user)
    extra = {"fcm_id": fcm_id, "web_fcm": None, "device_type": None}
    return ok("User logged-in!", staff_user_resource(school_db, user, school, extra_data=extra), token=token)


def revoke_token(db: Session, bearer: str | None) -> dict:
    if not bearer or "|" not in bearer:
        return fail("Unauthenticated.", code=401)
    token_id, plain = bearer.split("|", 1)
    row = db.get(PersonalAccessToken, int(token_id)) if token_id.isdigit() else None
    if row is None or row.token != hash_token(plain):
        return fail("Unauthenticated.", code=401)
    db.delete(row)
    db.commit()
    return ok("Logout Successfully")


def logout_user(
    db: Session,
    bearer: str | None,
    fcm_id: str | None = None,
    device_id: str | None = None,
    web_fcm: str | None = None,
) -> dict:
    user = find_token_user(db, bearer)
    if user is None:
        return fail("Unauthenticated.", code=401)
    if fcm_id or device_id or web_fcm or user.fcm_id:
        user.fcm_id = ""
        db.commit()
    return revoke_token(db, bearer)


def validation_error(message: str) -> dict:
    return fail(message, code=VALIDATION_ERROR)
