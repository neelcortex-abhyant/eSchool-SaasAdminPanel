from __future__ import annotations
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import sign_session, verify_password
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
    SystemSetting,
    User,
)


def _find_admin(db: Session, login: str, school_id: int | None) -> User | None:
    query = select(User).where((User.email == login) | (User.mobile == login), User.deleted_at.is_(None))
    if school_id is None:
        query = query.where(User.school_id.is_(None))
    else:
        query = query.where(User.school_id == school_id)
    return db.scalar(query)


def login_admin(central: Session, school_db: Session | None, school: School | None, login: str, password: str) -> tuple[dict, int]:
    db = school_db or central
    school_id = school.id if school is not None else None
    user = _find_admin(db, login, school_id)
    if user is None or not verify_password(password, user.password) or user.status != 1:
        return {"error": True, "message": "The provided credentials do not match our records."}, 401
    if school is None and user.school_id:
        return {"error": True, "message": "The provided credentials do not match our records."}, 401
    if school is not None and school.installed != 1:
        return {"error": True, "message": "Invalid school identifier."}, 422
    if school is not None and user.school_id is not None and user.school_id != school.id:
        return {"error": True, "message": "The provided credentials do not match our records."}, 401
    payload = {
        "uid": user.id,
        # Legacy cookie field; physical DB switching removed — school_id scopes data.
        "db": school.database_name if school else None,
        "code": school.code if school else None,
        "school_id": school.id if school else None,
    }
    requires_2fa = bool(user.two_factor_enabled) and not user.two_factor_secret
    return {
        "error": False,
        "message": "Logged in",
        "requires_2fa": requires_2fa,
        "token": sign_session(payload),
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "school_code": school.code if school else None,
        },
    }, 200


def maintenance_blocks(central: Session, school_code: str | None) -> bool:
    if not school_code:
        return False
    setting = central.scalar(select(SystemSetting).where(SystemSetting.name == "web_maintenance"))
    return bool(setting and setting.data == "1")


def scoped(query, model, school_id: int | None):
    if school_id is None or not hasattr(model, "school_id"):
        return query
    return query.where(model.school_id == school_id)


def rows(db: Session, model, school_id: int | None, serializer) -> list[dict]:
    query = scoped(select(model), model, school_id)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    return [serializer(row) for row in db.scalars(query)]


def count(db: Session, model, school_id: int | None) -> int:
    query = select(func.count()).select_from(model)
    query = scoped(query, model, school_id)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    return int(db.scalar(query) or 0)


def dashboard(db: Session, central: Session, school_id: int | None) -> dict:
    return {
        "students": count(db, Student, school_id),
        "classes": count(db, SchoolClass, school_id),
        "subjects": count(db, Subject, school_id),
        "attendances": count(db, Attendance, school_id),
        "exams": count(db, Exam, school_id),
        "fees": count(db, Fee, school_id),
        "announcements": count(db, Announcement, school_id),
        "leaves": count(db, Leave, school_id),
        "expenses": count(db, Expense, school_id),
        "schools": count(central, School, None),
        "packages": count(central, Package, None),
    }
