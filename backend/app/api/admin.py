from __future__ import annotations
from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import admin_context, central_db, close_admin_db, open_named_db
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
)
from app.services.admin_data import dashboard, login_admin, maintenance_blocks, rows
from app.services.mobile_auth import find_school

router = APIRouter()


class AdminLogin(BaseModel):
    email: str | None = None
    password: str | None = None
    code: str | None = None


def _student(row: Student) -> dict:
    return {
        "id": row.id,
        "admission_no": row.admission_no,
        "roll_number": row.roll_number,
        "class_section_id": row.class_section_id,
        "session_year_id": row.session_year_id,
        "user_id": row.user_id,
    }


def _class(row: SchoolClass) -> dict:
    return {"id": row.id, "name": row.name, "medium_id": row.medium_id}


def _subject(row: Subject) -> dict:
    return {"id": row.id, "name": row.name, "code": row.code, "type": row.type}


def _attendance(row: Attendance) -> dict:
    return {"id": row.id, "student_id": row.student_id, "type": row.type, "date": row.date.isoformat(), "remark": row.remark}


def _exam(row: Exam) -> dict:
    return {"id": row.id, "name": row.name, "class_id": row.class_id, "publish": row.publish}


def _fee(row: Fee) -> dict:
    return {"id": row.id, "name": row.name, "due_date": row.due_date.isoformat(), "due_charges": row.due_charges}


def _announcement(row: Announcement) -> dict:
    return {"id": row.id, "title": row.title, "description": row.description}


def _leave(row: Leave) -> dict:
    return {"id": row.id, "user_id": row.user_id, "reason": row.reason, "status": row.status}


def _expense(row: Expense) -> dict:
    return {"id": row.id, "title": row.title, "amount": row.amount, "date": row.date.isoformat()}


def _school(row: School) -> dict:
    return {"id": row.id, "name": row.name, "code": row.code, "status": row.status, "database_name": row.database_name}


def _package(row: Package) -> dict:
    return {"id": row.id, "name": row.name, "description": row.description, "status": row.status}


@router.post("/login")
def login(body: AdminLogin, response: Response, central: Session = Depends(central_db)):
    if not body.email or not body.password:
        return Response(
            content='{"error":true,"message":"Email and password are required."}',
            status_code=422,
            media_type="application/json",
        )
    if maintenance_blocks(central, body.code):
        return Response(content='{"error":true,"message":"System is under maintenance."}', status_code=503, media_type="application/json")
    school = None
    school_db = None
    if body.code:
        school = find_school(central, body.code)
        if school is None or school.installed != 1 or not school.database_name:
            response.status_code = 422
            return {"error": True, "message": "Invalid school identifier."}
        school_db = open_named_db(school.database_name)
    try:
        payload, status = login_admin(central, school_db, school, body.email, body.password)
    finally:
        if school_db is not None:
            school_db.close()
    if status != 200:
        response.status_code = status
        return payload
    if not payload.get("requires_2fa"):
        response.set_cookie("eschool_session", payload["token"], httponly=True, samesite="lax", path="/")
    return payload


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("eschool_session", path="/")
    return {"error": False, "message": "Logged out"}


@router.get("/me")
def me(request: Request, context=Depends(admin_context)):
    _db, user, _school_id = context
    try:
        return {
            "error": False,
            "data": {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "school_id": user.school_id,
            },
        }
    finally:
        close_admin_db(request)


def _guard(request: Request, context=Depends(admin_context)):
    return context


@router.get("/dashboard")
def dashboard_route(request: Request, central: Session = Depends(central_db), context=Depends(_guard)):
    db, _user, school_id = context
    try:
        return {"error": False, "data": dashboard(db, central, school_id)}
    finally:
        close_admin_db(request)


def _list(request: Request, model, serializer, context):
    db, _user, school_id = context
    try:
        return {"error": False, "data": rows(db, model, school_id, serializer)}
    finally:
        close_admin_db(request)


@router.get("/students")
def students(request: Request, context=Depends(_guard)):
    return _list(request, Student, _student, context)


@router.get("/classes")
def classes(request: Request, context=Depends(_guard)):
    return _list(request, SchoolClass, _class, context)


@router.get("/subjects")
def subjects(request: Request, context=Depends(_guard)):
    return _list(request, Subject, _subject, context)


@router.get("/attendances")
def attendances(request: Request, context=Depends(_guard)):
    return _list(request, Attendance, _attendance, context)


@router.get("/exams")
def exams(request: Request, context=Depends(_guard)):
    return _list(request, Exam, _exam, context)


@router.get("/fees")
def fees(request: Request, context=Depends(_guard)):
    return _list(request, Fee, _fee, context)


@router.get("/announcements")
def announcements(request: Request, context=Depends(_guard)):
    return _list(request, Announcement, _announcement, context)


@router.get("/leaves")
def leaves(request: Request, context=Depends(_guard)):
    return _list(request, Leave, _leave, context)


@router.get("/expenses")
def expenses(request: Request, context=Depends(_guard)):
    return _list(request, Expense, _expense, context)


@router.get("/schools")
def schools(request: Request, central: Session = Depends(central_db), context=Depends(_guard)):
    try:
        return {"error": False, "data": rows(central, School, None, _school)}
    finally:
        close_admin_db(request)


@router.get("/packages")
def packages(request: Request, central: Session = Depends(central_db), context=Depends(_guard)):
    try:
        return {"error": False, "data": rows(central, Package, None, _package)}
    finally:
        close_admin_db(request)
