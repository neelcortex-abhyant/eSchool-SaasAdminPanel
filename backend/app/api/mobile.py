from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Header, Request
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.core.responses import INVALID_LOGIN, fail
from app.services.mobile_auth import (
    find_school,
    login_parent,
    login_student,
    login_teacher,
    logout_user,
    validation_error,
)

router = APIRouter()


def _resolve_school(central: Session, code: str):
    school = find_school(central, code)
    if school is None or school.deleted_at is not None or school.installed != 1:
        return None
    return school


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()


@router.post("/student/login")
async def student_login(
    gr_number: str | None = Form(default=None),
    password: str | None = Form(default=None),
    school_code: str | None = Form(default=None),
    fcm_id: str | None = Form(default=None),
    central: Session = Depends(central_db),
):
    if not gr_number:
        return validation_error("The GR number is required.")
    if not password:
        return validation_error("The password is required.")
    if not school_code:
        return validation_error("The school code is required.")
    if not school_code.isalnum():
        return validation_error("The school code must contain only letters and numbers.")
    school = _resolve_school(central, school_code)
    if school is None:
        return fail("Invalid Login Credentials", code=INVALID_LOGIN)
    return login_student(central, central, school, gr_number, password, fcm_id)


@router.post("/parent/login")
async def parent_login(
    email: str | None = Form(default=None),
    password: str | None = Form(default=None),
    school_code: str | None = Form(default=None),
    fcm_id: str | None = Form(default=None),
    central: Session = Depends(central_db),
):
    if not school_code:
        return validation_error("The school code is required.")
    if not email:
        return validation_error("The email field cannot be empty.")
    if "@" not in email:
        return validation_error("Please provide a valid email address.")
    if not password:
        return validation_error("The password field cannot be empty.")
    school = _resolve_school(central, school_code)
    if school is None:
        return fail("Invalid Login Credentials", code=INVALID_LOGIN)
    return login_parent(central, school, email, password, fcm_id)


@router.post("/teacher/login")
@router.post("/staff/login")
async def teacher_login(
    email: str | None = Form(default=None),
    password: str | None = Form(default=None),
    school_code: str | None = Form(default=None),
    fcm_id: str | None = Form(default=None),
    central: Session = Depends(central_db),
):
    if school_code is None:
        return validation_error("The school code is mandatory.")
    if not email:
        return validation_error("The email field cannot be empty.")
    if "@" not in email:
        return validation_error("Please provide a valid email address.")
    if not password:
        return validation_error("The password field cannot be empty.")
    school = _resolve_school(central, school_code)
    if school is None:
        return fail("Invalid school code", code=INVALID_LOGIN)
    return login_teacher(central, school, email, password, fcm_id)


@router.post("/logout")
async def logout(
    request: Request,
    school_code: str | None = Header(default=None, alias="school-code"),
    authorization: str | None = Header(default=None),
    central: Session = Depends(central_db),
):
    if not school_code:
        return fail("School Code is Required", code=102)
    school = _resolve_school(central, school_code)
    if school is None:
        return fail("Invalid school code", code=102)
    fcm_id = device_id = web_fcm = None
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        fcm_id = form.get("fcm_id")
        device_id = form.get("device_id")
        web_fcm = form.get("web_fcm")
    return logout_user(
        central,
        bearer=_bearer(authorization),
        fcm_id=str(fcm_id) if fcm_id else None,
        device_id=str(device_id) if device_id else None,
        web_fcm=str(web_fcm) if web_fcm else None,
    )
