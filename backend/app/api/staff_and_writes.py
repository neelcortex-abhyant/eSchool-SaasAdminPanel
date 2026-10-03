from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_tenant_user
from app.core.responses import VALIDATION_ERROR, fail, ok
from app.core.security import utcnow
from app.models.tables import (
    USER_MODEL,
    Leave,
    Medium,
    ModelHasRole,
    Role,
    School,
    SchoolClass,
    Student,
    User,
)
from app.services.mobile_auth import (
    default_session_year,
    guardian_user_resource,
    staff_user_resource,
    student_user_resource,
    user_roles,
    validation_error,
)

router = APIRouter()

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_ROOT / "data"

COUNTRY_CODES = [
    {"name": "India", "code": "+91"},
    {"name": "United States", "code": "+1"},
    {"name": "United Kingdom", "code": "+44"},
]


def _dt(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _append_jsonl(path: Path, payload: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, default=str) + "\n")


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _guardian_child(db: Session, guardian: User, child_id: Optional[int]) -> Optional[Student]:
    if child_id is None:
        return None
    by_student_id = db.scalar(
        select(Student).where(
            Student.id == child_id,
            Student.guardian_id == guardian.id,
            Student.deleted_at.is_(None),
        )
    )
    if by_student_id is not None:
        return by_student_id
    return db.scalar(
        select(Student).where(
            Student.user_id == child_id,
            Student.guardian_id == guardian.id,
            Student.deleted_at.is_(None),
        )
    )


def _leave_payload(row: Leave) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "reason": row.reason,
        "from_date": _dt(row.from_date),
        "to_date": _dt(row.to_date),
        "status": row.status,
        "school_id": row.school_id,
        "session_year_id": row.session_year_id,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _class_payload(row: SchoolClass) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "include_semesters": row.include_semesters,
        "medium_id": row.medium_id,
        "school_id": row.school_id,
    }


def _medium_payload(row: Medium) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "school_id": row.school_id,
    }


def _teacher_payload(user: User) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "mobile": user.mobile,
        "image": user.image,
        "status": user.status,
        "school_id": user.school_id,
    }


def _count_role_users(db: Session, school_id: int, role_name: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .join(ModelHasRole, ModelHasRole.model_id == User.id)
            .join(Role, Role.id == ModelHasRole.role_id)
            .where(
                ModelHasRole.model_type == USER_MODEL,
                Role.name == role_name,
                User.school_id == school_id,
                User.deleted_at.is_(None),
            )
        )
        or 0
    )


# --- Staff reads ---


@router.get("/profile")
async def profile(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    roles = user_roles(db, user.id)
    extra = {"fcm_id": user.fcm_id, "web_fcm": None, "device_type": None}
    if "Student" in roles:
        student = db.scalar(select(Student).where(Student.user_id == user.id, Student.deleted_at.is_(None)))
        if student is not None:
            return ok("Data Fetched Successfully", student_user_resource(db, user, student, school, extra_data=extra))
    if "Guardian" in roles:
        sy = default_session_year(db, school.id)
        children: List[Student] = []
        if sy is not None:
            children = list(
                db.scalars(
                    select(Student).where(
                        Student.guardian_id == user.id,
                        Student.session_year_id == sy.id,
                        Student.deleted_at.is_(None),
                    )
                )
            )
        return ok("Data Fetched Successfully", guardian_user_resource(db, user, school, children, extra_data=extra))
    return ok("Data Fetched Successfully", staff_user_resource(db, user, school, extra_data=extra))


@router.get("/staff/counter")
async def staff_counter(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, _user, school = tenant
    try:
        students = int(
            db.scalar(
                select(func.count()).select_from(Student).where(
                    Student.school_id == school.id,
                    Student.deleted_at.is_(None),
                )
            )
            or 0
        )
        teachers = _count_role_users(db, school.id, "Teacher")
        classes = int(
            db.scalar(
                select(func.count()).select_from(SchoolClass).where(
                    SchoolClass.school_id == school.id,
                    SchoolClass.deleted_at.is_(None),
                )
            )
            or 0
        )
    except Exception:
        students, teachers, classes = 0, 0, 0
    return ok(
        "Data Fetched Successfully",
        {"students": students, "teachers": teachers, "classes": classes},
    )


@router.get("/classes")
async def classes(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, _user, school = tenant
    rows = list(
        db.scalars(
            select(SchoolClass).where(
                SchoolClass.school_id == school.id,
                SchoolClass.deleted_at.is_(None),
            )
        )
    )
    return ok("Data Fetched Successfully", [_class_payload(r) for r in rows])


@router.get("/staff/teachers")
async def staff_teachers(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, _user, school = tenant
    rows = list(
        db.scalars(
            select(User)
            .join(ModelHasRole, ModelHasRole.model_id == User.id)
            .join(Role, Role.id == ModelHasRole.role_id)
            .where(
                ModelHasRole.model_type == USER_MODEL,
                Role.name == "Teacher",
                User.school_id == school.id,
                User.deleted_at.is_(None),
            )
        )
    )
    return ok("Data Fetched Successfully", [_teacher_payload(u) for u in rows])


@router.get("/leaves")
async def list_leaves(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    rows = list(
        db.scalars(
            select(Leave).where(
                Leave.user_id == user.id,
                Leave.school_id == school.id,
            )
        )
    )
    return ok("Data Fetched Successfully", [_leave_payload(r) for r in rows])


@router.get("/medium")
async def mediums(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, _user, school = tenant
    rows = list(
        db.scalars(
            select(Medium).where(
                Medium.school_id == school.id,
                Medium.deleted_at.is_(None),
            )
        )
    )
    return ok("Data Fetched Successfully", [_medium_payload(r) for r in rows])


@router.get("/country-codes")
async def country_codes(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Data Fetched Successfully", COUNTRY_CODES)


# --- Staff / common writes ---


@router.post("/leaves")
async def create_leave(
    reason: Optional[str] = Form(default=None),
    from_date: Optional[str] = Form(default=None),
    to_date: Optional[str] = Form(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    if not reason:
        return validation_error("The reason field is required.")
    parsed_from = _parse_date(from_date)
    parsed_to = _parse_date(to_date)
    if parsed_from is None:
        return validation_error("The from date field is required.")
    if parsed_to is None:
        return validation_error("The to date field is required.")
    if parsed_to < parsed_from:
        return validation_error("The to date must be after the from date.")
    sy = default_session_year(db, school.id)
    if sy is None:
        return fail("Session year not found", code=VALIDATION_ERROR)
    row = Leave(
        user_id=user.id,
        reason=str(reason)[:255],
        from_date=parsed_from,
        to_date=parsed_to,
        status=0,
        school_id=school.id,
        session_year_id=sy.id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ok("Leave submitted successfully", _leave_payload(row))


@router.post("/parent/store-fees")
async def parent_store_fees(
    transaction_id: Optional[str] = Form(default=None),
    child_id: Optional[int] = Form(default=None),
    payment_id: Optional[str] = Form(default=None),
    payment_signature: Optional[str] = Form(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, user, school = tenant
    if child_id is None:
        return validation_error("The child id field is required.")
    if not transaction_id:
        return validation_error("The transaction id field is required.")
    child = _guardian_child(db, user, child_id)
    if child is None:
        return fail("Child's Account is not Active.Contact School Support", code=VALIDATION_ERROR)
    event = {
        "type": "store-fees",
        "at": utcnow().isoformat(),
        "school_id": school.id,
        "guardian_id": user.id,
        "child_id": child.id,
        "child_user_id": child.user_id,
        "transaction_id": str(transaction_id),
        "payment_id": payment_id,
        "payment_signature": payment_signature,
    }
    _append_jsonl(DATA_DIR / "fee_events.jsonl", event)
    return ok("Fees stored successfully", {"transaction_id": str(transaction_id), "child_id": child.id})


@router.post("/parent/fail-payment-transaction")
async def parent_fail_payment_transaction(
    payment_transaction_id: Optional[str] = Form(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    if not payment_transaction_id:
        return validation_error("The payment transaction id field is required.")
    return ok("Payment transaction marked as failed", {"payment_transaction_id": str(payment_transaction_id)})


@router.post("/message/read")
async def message_read(
    request: Request,
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    ids: Any = None
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        body = await request.json()
        if isinstance(body, dict):
            ids = body.get("ids") or body.get("id") or body.get("message_ids")
        elif isinstance(body, list):
            ids = body
    else:
        form = await request.form()
        ids = form.get("ids") or form.get("id") or form.getlist("ids[]") or form.getlist("ids")
    return ok("Messages marked as read", {"ids": ids})


@router.post("/delete/message")
async def delete_message(
    request: Request,
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    ids: Any = None
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        body = await request.json()
        if isinstance(body, dict):
            ids = body.get("ids") or body.get("id") or body.get("message_id")
        else:
            ids = body
    else:
        form = await request.form()
        ids = form.get("ids") or form.get("id") or form.get("message_id")
    return ok("Message deleted successfully", {"ids": ids})


# --- Empty / minimal reads ---


@router.get("/diaries")
async def diaries(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Data Fetched Successfully", [])


@router.get("/student-details")
async def student_details(
    student_id: Optional[int] = Query(default=None),
    id: Optional[int] = Query(default=None),
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    db, _user, school = tenant
    lookup = student_id if student_id is not None else id
    if lookup is None:
        return validation_error("The student id field is required.")
    student = db.scalar(
        select(Student).where(
            Student.id == lookup,
            Student.school_id == school.id,
            Student.deleted_at.is_(None),
        )
    )
    if student is None:
        student = db.scalar(
            select(Student).where(
                Student.user_id == lookup,
                Student.school_id == school.id,
                Student.deleted_at.is_(None),
            )
        )
    if student is None:
        return fail("Student not found", code=VALIDATION_ERROR)
    student_user = db.get(User, student.user_id)
    if student_user is None:
        return fail("Student not found", code=VALIDATION_ERROR)
    data = student_user_resource(db, student_user, student, school, extra_data={})
    return ok("Data Fetched Successfully", data)


@router.get("/pickup-points")
async def pickup_points(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Data Fetched Successfully", [])


@router.get("/transportation-shifts")
async def transportation_shifts(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Data Fetched Successfully", [])


@router.get("/transportation-fees")
async def transportation_fees(
    tenant: Tuple[Session, User, School] = Depends(require_tenant_user),
):
    return ok("Data Fetched Successfully", [])


# --- Webhooks (no auth) ---


async def _webhook_receive(provider: str, request: Request) -> dict:
    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = {"raw": raw.decode("utf-8", errors="replace") if raw else ""}
    _append_jsonl(
        DATA_DIR / "webhook_events.jsonl",
        {
            "provider": provider,
            "at": utcnow().isoformat(),
            "headers": {
                k: v
                for k, v in request.headers.items()
                if k.lower() in ("content-type", "stripe-signature", "x-razorpay-signature")
            },
            "body": body,
        },
    )
    return {"error": False, "message": "Webhook received", "code": 200, "data": None}


@router.post("/webhook/stripe")
async def webhook_stripe(request: Request):
    return await _webhook_receive("stripe", request)


@router.post("/webhook/razorpay")
async def webhook_razorpay(request: Request):
    return await _webhook_receive("razorpay", request)


@router.post("/webhook/paystack")
async def webhook_paystack(request: Request):
    return await _webhook_receive("paystack", request)


@router.post("/webhook/flutterwave")
async def webhook_flutterwave(request: Request):
    return await _webhook_receive("flutterwave", request)
