"""School Admin academic management wave routes (mounted under /school-admin)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_school_permission
from app.services.v1 import rbac
from app.services.v1 import school_academic_mgmt as mgmt
from app.services.v1.school_academics import AcademicError

router = APIRouter(prefix="")

require_exams = require_school_permission(rbac.PERM_EXAMS)
require_students = require_school_permission(rbac.PERM_STUDENTS)
require_fees = require_school_permission(rbac.PERM_FEES)
require_school = require_school_permission(rbac.PERM_SCHOOL)
require_staff = require_school_permission(rbac.PERM_STAFF)
require_attendance = require_school_permission(rbac.PERM_ATTENDANCE)
require_reports = require_school_permission(rbac.PERM_REPORTS)
require_dashboard = require_school_permission(rbac.PERM_DASHBOARD)


class Body(BaseModel):
    model_config = ConfigDict(extra="allow")


def _school_id(auth: AuthContext) -> int:
    return int(auth.user.school_id)  # type: ignore[arg-type]


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def _body(body: Body) -> dict[str, Any]:
    return mgmt.sanitize_body(body.model_dump(exclude_unset=True))


# ---- Grading scales ----


@router.get("/grading-scales")
def list_grading_scales(
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_grading_scales(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/grading-scales", status_code=status.HTTP_201_CREATED)
def create_grading_scale(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_grading_scale(db, _school_id(auth), _body(body)))


@router.get("/grading-scales/{scale_id}")
def get_grading_scale(
    scale_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_grading_scale(db, _school_id(auth), scale_id))


@router.patch("/grading-scales/{scale_id}")
def patch_grading_scale(
    scale_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_grading_scale(db, _school_id(auth), scale_id, _body(body)))


@router.delete("/grading-scales/{scale_id}")
def delete_grading_scale(
    scale_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_grading_scale(db, _school_id(auth), scale_id))


# ---- Report cards ----


@router.get("/report-cards")
def list_report_cards(
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    exam_id: int | None = Query(None, ge=1),
    student_id: int | None = Query(None, ge=1),
):
    return _run(
        lambda: mgmt.list_report_cards(
            db, _school_id(auth), page=page, page_size=page_size, exam_id=exam_id, student_id=student_id
        )
    )


@router.post("/report-cards", status_code=status.HTTP_201_CREATED)
def generate_report_cards(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _body(body)
    exam_id = int(data.get("exam_id") or 0)
    if not exam_id:
        raise HTTPException(status_code=422, detail="exam_id is required")
    scale_id = int(data["grading_scale_id"]) if data.get("grading_scale_id") is not None else None
    return _run(lambda: mgmt.generate_report_cards(db, _school_id(auth), exam_id, scale_id))


@router.get("/report-cards/{report_id}")
def get_report_card(
    report_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_report_card(db, _school_id(auth), report_id))


# ---- Question bank ----


@router.get("/question-bank")
def list_question_bank(
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    subject_id: int | None = Query(None, ge=1),
    q: str = Query(""),
):
    return _run(
        lambda: mgmt.list_question_bank(
            db, _school_id(auth), page=page, page_size=page_size, subject_id=subject_id, q=q
        )
    )


@router.post("/question-bank", status_code=status.HTTP_201_CREATED)
def create_question_bank(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_question_bank(db, _school_id(auth), _body(body)))


@router.get("/question-bank/{question_id}")
def get_question_bank(
    question_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_question_bank(db, _school_id(auth), question_id))


@router.patch("/question-bank/{question_id}")
def patch_question_bank(
    question_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_question_bank(db, _school_id(auth), question_id, _body(body)))


@router.delete("/question-bank/{question_id}")
def delete_question_bank(
    question_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_question_bank(db, _school_id(auth), question_id))


@router.post("/online-assessments/{assessment_id}/questions/from-bank", status_code=status.HTTP_201_CREATED)
def copy_from_bank(
    assessment_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _body(body)
    ids = data.get("question_ids") or []
    return _run(lambda: mgmt.copy_questions_to_assessment(db, _school_id(auth), assessment_id, ids))


# ---- Admission inquiries / holidays ----


@router.get("/admission-inquiries")
def list_admission_inquiries(
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    status_filter: str | None = Query(None, alias="status"),
):
    return _run(
        lambda: mgmt.list_admission_inquiries(
            db, _school_id(auth), page=page, page_size=page_size, status=status_filter
        )
    )


@router.post("/admission-inquiries", status_code=status.HTTP_201_CREATED)
def create_admission_inquiry(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_admission_inquiry(db, _school_id(auth), _body(body)))


@router.patch("/admission-inquiries/{row_id}")
def patch_admission_inquiry(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_admission_inquiry(db, _school_id(auth), row_id, _body(body)))


@router.delete("/admission-inquiries/{row_id}")
def delete_admission_inquiry(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_admission_inquiry(db, _school_id(auth), row_id))


@router.get("/holidays")
def list_holidays(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_holidays(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/holidays", status_code=status.HTTP_201_CREATED)
def create_holiday(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_holiday(db, _school_id(auth), _body(body)))


@router.patch("/holidays/{row_id}")
def patch_holiday(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_holiday(db, _school_id(auth), row_id, _body(body)))


@router.delete("/holidays/{row_id}")
def delete_holiday(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_holiday(db, _school_id(auth), row_id))


# ---- Students extras ----


@router.post("/students/import", status_code=status.HTTP_201_CREATED)
def import_students(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _body(body)
    rows = data.get("rows") or data.get("students") or data.get("items") or []
    return _run(lambda: mgmt.bulk_import_students(db, _school_id(auth), rows))


@router.post("/students/promote")
def promote_students(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.promote_students(db, _school_id(auth), _body(body)))


@router.post("/students/{student_id}/transfer")
def transfer_student(
    student_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.transfer_student(db, _school_id(auth), student_id, _body(body)))


@router.post("/students/{student_id}/reset-password")
def reset_student_password(
    student_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.reset_student_password(db, _school_id(auth), student_id, _body(body)))


@router.get("/students/{student_id}/electives")
def list_electives(
    student_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.list_student_electives(db, _school_id(auth), student_id))


@router.post("/students/{student_id}/electives", status_code=status.HTTP_201_CREATED)
def assign_elective(
    student_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.assign_student_elective(db, _school_id(auth), student_id, _body(body)))


@router.delete("/students/{student_id}/electives/{elective_id}")
def remove_elective(
    student_id: int,
    elective_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.remove_student_elective(db, _school_id(auth), student_id, elective_id))


# ---- Fees ----


@router.get("/fee-types")
def list_fee_types(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_fee_types(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/fee-types", status_code=status.HTTP_201_CREATED)
def create_fee_type(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_fee_type(db, _school_id(auth), _body(body)))


@router.patch("/fee-types/{row_id}")
def patch_fee_type(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_fee_type(db, _school_id(auth), row_id, _body(body)))


@router.delete("/fee-types/{row_id}")
def delete_fee_type(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_fee_type(db, _school_id(auth), row_id))


@router.get("/fee-structures")
def list_fee_structures(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_fee_structures(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/fee-structures", status_code=status.HTTP_201_CREATED)
def create_fee_structure(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_fee_structure(db, _school_id(auth), _body(body)))


@router.get("/fee-structures/{row_id}")
def get_fee_structure(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_fee_structure(db, _school_id(auth), row_id))


@router.patch("/fee-structures/{row_id}")
def patch_fee_structure(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_fee_structure(db, _school_id(auth), row_id, _body(body)))


@router.delete("/fee-structures/{row_id}")
def delete_fee_structure(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_fee_structure(db, _school_id(auth), row_id))


@router.get("/fee-assignments")
def list_fee_assignments(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    student_id: int | None = Query(None, ge=1),
    structure_id: int | None = Query(None, ge=1),
):
    return _run(
        lambda: mgmt.list_fee_assignments(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            student_id=student_id,
            structure_id=structure_id,
        )
    )


@router.post("/fee-assignments", status_code=status.HTTP_201_CREATED)
def create_fee_assignment(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_fee_assignment(db, _school_id(auth), _body(body)))


@router.delete("/fee-assignments/{row_id}")
def delete_fee_assignment(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_fee_assignment(db, _school_id(auth), row_id))


@router.get("/fee-concessions")
def list_fee_concessions(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_fee_concessions(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/fee-concessions", status_code=status.HTTP_201_CREATED)
def create_fee_concession(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_fee_concession(db, _school_id(auth), _body(body)))


@router.delete("/fee-concessions/{row_id}")
def delete_fee_concession(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_fee_concession(db, _school_id(auth), row_id))


@router.get("/fee-payments")
def list_fee_payments(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    student_id: int | None = Query(None, ge=1),
):
    return _run(
        lambda: mgmt.list_fee_payments(
            db, _school_id(auth), page=page, page_size=page_size, student_id=student_id
        )
    )


@router.get("/fees/outstanding")
def fees_outstanding(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.fees_outstanding(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/fees/collect", status_code=status.HTTP_201_CREATED)
def fees_collect(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.collect_fee(db, _school_id(auth), _body(body)))


# ---- Semesters / streams / shifts / syllabi / online classes ----


@router.get("/semesters")
def list_semesters(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_semesters(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/semesters", status_code=status.HTTP_201_CREATED)
def create_semester(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_semester(db, _school_id(auth), _body(body)))


@router.patch("/semesters/{row_id}")
def patch_semester(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_semester(db, _school_id(auth), row_id, _body(body)))


@router.delete("/semesters/{row_id}")
def delete_semester(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_semester(db, _school_id(auth), row_id))


@router.get("/streams")
def list_streams(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_streams(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/streams", status_code=status.HTTP_201_CREATED)
def create_stream(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_stream(db, _school_id(auth), _body(body)))


@router.patch("/streams/{row_id}")
def patch_stream(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_stream(db, _school_id(auth), row_id, _body(body)))


@router.delete("/streams/{row_id}")
def delete_stream(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_stream(db, _school_id(auth), row_id))


@router.get("/shifts")
def list_shifts(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_shifts(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
def create_shift(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_shift(db, _school_id(auth), _body(body)))


@router.patch("/shifts/{row_id}")
def patch_shift(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_shift(db, _school_id(auth), row_id, _body(body)))


@router.delete("/shifts/{row_id}")
def delete_shift(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_shift(db, _school_id(auth), row_id))


@router.get("/syllabi")
def list_syllabi(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_syllabi(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/syllabi", status_code=status.HTTP_201_CREATED)
def create_syllabus(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_syllabus(db, _school_id(auth), _body(body)))


@router.patch("/syllabi/{row_id}")
def patch_syllabus(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_syllabus(db, _school_id(auth), row_id, _body(body)))


@router.delete("/syllabi/{row_id}")
def delete_syllabus(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_syllabus(db, _school_id(auth), row_id))


@router.get("/online-classes")
def list_online_classes(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_online_classes(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/online-classes", status_code=status.HTTP_201_CREATED)
def create_online_class(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_online_class(db, _school_id(auth), _body(body)))


@router.patch("/online-classes/{row_id}")
def patch_online_class(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_online_class(db, _school_id(auth), row_id, _body(body)))


@router.delete("/online-classes/{row_id}")
def delete_online_class(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_online_class(db, _school_id(auth), row_id))


# ---- Staff bulk upload + role permissions ----


@router.get("/staff-roles")
def list_staff_roles(
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.list_staff_roles(db, _school_id(auth)))


@router.get("/staff/{user_id}/roles")
def get_staff_roles(
    user_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_staff_user_roles(db, _school_id(auth), user_id))


@router.put("/staff/{user_id}/roles")
def put_staff_roles(
    user_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _body(body)
    roles = data.get("roles") or []
    if not isinstance(roles, list):
        raise HTTPException(status_code=422, detail="roles must be a list of role names")
    return _run(lambda: mgmt.set_staff_user_roles(db, _school_id(auth), user_id, roles))


@router.post("/staff/import", status_code=status.HTTP_201_CREATED)
def import_staff(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _body(body)
    rows = data.get("rows") or data.get("items") or []
    if not isinstance(rows, list):
        raise HTTPException(status_code=422, detail="rows must be a list")
    return _run(lambda: mgmt.bulk_import_staff(db, _school_id(auth), rows))


# ---- Staff attendance / QR / tasks ----


@router.post("/staff-attendance", status_code=status.HTTP_201_CREATED)
def mark_staff_attendance(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.mark_staff_attendance(db, _school_id(auth), _body(body)))


@router.get("/staff-attendance/today")
def staff_attendance_today(
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.staff_attendance_today(db, _school_id(auth)))


@router.get("/staff-attendance/register")
def staff_attendance_register(
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
    attendance_date: date | None = Query(None),
):
    return _run(lambda: mgmt.staff_attendance_register(db, _school_id(auth), attendance_date))


@router.get("/staff-attendance/reports")
def staff_attendance_reports(
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
):
    return _run(
        lambda: mgmt.staff_attendance_report(db, _school_id(auth), from_date=from_date, to_date=to_date)
    )


@router.get("/staff-qr-attendance-settings")
def get_staff_qr_settings(
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_staff_qr_settings(db, _school_id(auth)))


@router.put("/staff-qr-attendance-settings")
def put_staff_qr_settings(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.put_staff_qr_settings(db, _school_id(auth), _body(body)))


@router.get("/staff-tasks")
def list_staff_tasks(
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_staff_tasks(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/staff-tasks", status_code=status.HTTP_201_CREATED)
def create_staff_task(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_staff_task(db, _school_id(auth), _body(body)))


@router.patch("/staff-tasks/{row_id}")
def patch_staff_task(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_staff_task(db, _school_id(auth), row_id, _body(body)))


@router.delete("/staff-tasks/{row_id}")
def delete_staff_task(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_staff_task(db, _school_id(auth), row_id))


# ---- Expense / income / payroll ----


@router.get("/expense-categories")
def list_expense_categories(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_expense_categories(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/expense-categories", status_code=status.HTTP_201_CREATED)
def create_expense_category(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_expense_category(db, _school_id(auth), _body(body)))


@router.patch("/expense-categories/{row_id}")
def patch_expense_category(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_expense_category(db, _school_id(auth), row_id, _body(body)))


@router.delete("/expense-categories/{row_id}")
def delete_expense_category(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_expense_category(db, _school_id(auth), row_id))


@router.get("/income-categories")
def list_income_categories(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_income_categories(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/income-categories", status_code=status.HTTP_201_CREATED)
def create_income_category(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_income_category(db, _school_id(auth), _body(body)))


@router.delete("/income-categories/{row_id}")
def delete_income_category(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_income_category(db, _school_id(auth), row_id))


@router.get("/incomes/dashboard")
def incomes_dashboard(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.incomes_dashboard(db, _school_id(auth)))


@router.get("/incomes")
def list_incomes(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_incomes(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/incomes", status_code=status.HTTP_201_CREATED)
def create_income(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_income(db, _school_id(auth), _body(body)))


@router.patch("/incomes/{row_id}")
def patch_income(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_income(db, _school_id(auth), row_id, _body(body)))


@router.delete("/incomes/{row_id}")
def delete_income(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_income(db, _school_id(auth), row_id))


@router.get("/payroll-settings")
def get_payroll_settings(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_payroll_settings(db, _school_id(auth)))


@router.put("/payroll-settings")
def put_payroll_settings(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.put_payroll_settings(db, _school_id(auth), _body(body)))


@router.get("/payroll-runs")
def list_payroll_runs(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_payroll_runs(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/payroll-runs", status_code=status.HTTP_201_CREATED)
def create_payroll_run(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_payroll_run(db, _school_id(auth), _body(body)))


# ---- Transport ----


@router.get("/vehicles")
def list_vehicles(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_vehicles(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/vehicles", status_code=status.HTTP_201_CREATED)
def create_vehicle(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_vehicle(db, _school_id(auth), _body(body)))


@router.patch("/vehicles/{row_id}")
def patch_vehicle(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_vehicle(db, _school_id(auth), row_id, _body(body)))


@router.delete("/vehicles/{row_id}")
def delete_vehicle(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_vehicle(db, _school_id(auth), row_id))


@router.get("/transport-routes")
def list_transport_routes(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_transport_routes(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/transport-routes", status_code=status.HTTP_201_CREATED)
def create_transport_route(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_transport_route(db, _school_id(auth), _body(body)))


@router.patch("/transport-routes/{row_id}")
def patch_transport_route(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_transport_route(db, _school_id(auth), row_id, _body(body)))


@router.delete("/transport-routes/{row_id}")
def delete_transport_route(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_transport_route(db, _school_id(auth), row_id))


@router.get("/transport-stops")
def list_transport_stops(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    route_id: int | None = Query(None, ge=1),
):
    return _run(
        lambda: mgmt.list_transport_stops(
            db, _school_id(auth), page=page, page_size=page_size, route_id=route_id
        )
    )


@router.post("/transport-stops", status_code=status.HTTP_201_CREATED)
def create_transport_stop(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_transport_stop(db, _school_id(auth), _body(body)))


@router.delete("/transport-stops/{row_id}")
def delete_transport_stop(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_transport_stop(db, _school_id(auth), row_id))


@router.get("/student-transport-assignments")
def list_student_transport_assignments(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(
        lambda: mgmt.list_student_transport_assignments(
            db, _school_id(auth), page=page, page_size=page_size
        )
    )


@router.post("/student-transport-assignments", status_code=status.HTTP_201_CREATED)
def create_student_transport_assignment(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_student_transport_assignment(db, _school_id(auth), _body(body)))


@router.delete("/student-transport-assignments/{row_id}")
def delete_student_transport_assignment(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_student_transport_assignment(db, _school_id(auth), row_id))


# ---- Certificates / ID cards ----


@router.get("/certificate-templates")
def list_certificate_templates(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(
        lambda: mgmt.list_certificate_templates(db, _school_id(auth), page=page, page_size=page_size)
    )


@router.post("/certificate-templates", status_code=status.HTTP_201_CREATED)
def create_certificate_template(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_certificate_template(db, _school_id(auth), _body(body)))


@router.patch("/certificate-templates/{row_id}")
def patch_certificate_template(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_certificate_template(db, _school_id(auth), row_id, _body(body)))


@router.delete("/certificate-templates/{row_id}")
def delete_certificate_template(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_certificate_template(db, _school_id(auth), row_id))


@router.post("/certificates/issue", status_code=status.HTTP_201_CREATED)
def issue_certificate(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.issue_certificate(db, _school_id(auth), _body(body)))


@router.get("/id-card-settings")
def get_id_card_settings(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_id_card_settings(db, _school_id(auth)))


@router.put("/id-card-settings")
def put_id_card_settings(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.put_id_card_settings(db, _school_id(auth), _body(body)))


@router.get("/students/{student_id}/id-card")
def student_id_card(
    student_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.student_id_card_payload(db, _school_id(auth), student_id))


@router.get("/staff/{staff_id}/id-card")
def staff_id_card(
    staff_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.staff_id_card_payload(db, _school_id(auth), staff_id))


# ---- Reports ----


@router.get("/reports/students")
def reports_students(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_students(db, _school_id(auth)))


@router.get("/reports/teachers")
def reports_teachers(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_teachers(db, _school_id(auth)))


@router.get("/reports/staff")
def reports_staff(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_staff(db, _school_id(auth)))


@router.get("/reports/exams")
def reports_exams(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_exams(db, _school_id(auth)))


@router.get("/reports/expenses")
def reports_expenses(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_expenses(db, _school_id(auth)))


@router.get("/reports/income")
def reports_income(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_income(db, _school_id(auth)))


@router.get("/reports/financial-summary")
def reports_financial_summary(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_financial_summary(db, _school_id(auth)))


# ---- Diary / notifications / announcements / sliders / gallery ----


@router.get("/diary-categories")
def list_diary_categories(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_diary_categories(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/diary-categories", status_code=status.HTTP_201_CREATED)
def create_diary_category(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_diary_category(db, _school_id(auth), _body(body)))


@router.delete("/diary-categories/{row_id}")
def delete_diary_category(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_diary_category(db, _school_id(auth), row_id))


@router.get("/student-diaries")
def list_student_diaries(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    student_id: int | None = Query(None, ge=1),
):
    return _run(
        lambda: mgmt.list_student_diaries(
            db, _school_id(auth), page=page, page_size=page_size, student_id=student_id
        )
    )


@router.post("/student-diaries", status_code=status.HTTP_201_CREATED)
def create_student_diary(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_student_diary(db, _school_id(auth), _body(body)))


@router.delete("/student-diaries/{row_id}")
def delete_student_diary(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_student_diary(db, _school_id(auth), row_id))


@router.get("/notifications")
def list_notifications(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_notifications(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/notifications", status_code=status.HTTP_201_CREATED)
def create_notification(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: mgmt.create_notification(
            db, _school_id(auth), _body(body), created_by=str(auth.user.id)
        )
    )


@router.get("/announcements")
def list_announcements(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_announcements(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/announcements", status_code=status.HTTP_201_CREATED)
def create_announcement(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_announcement(db, _school_id(auth), _body(body)))


@router.get("/sliders")
def list_sliders(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_sliders(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/sliders", status_code=status.HTTP_201_CREATED)
def create_slider(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_slider(db, _school_id(auth), _body(body)))


@router.patch("/sliders/{row_id}")
def patch_slider(
    row_id: int,
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_slider(db, _school_id(auth), row_id, _body(body)))


@router.delete("/sliders/{row_id}")
def delete_slider(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_slider(db, _school_id(auth), row_id))


@router.get("/gallery")
def list_gallery(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_gallery(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/gallery", status_code=status.HTTP_201_CREATED)
def create_gallery_item(
    body: Body,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_gallery_item(db, _school_id(auth), _body(body)))


@router.delete("/gallery/{row_id}")
def delete_gallery_item(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_gallery_item(db, _school_id(auth), row_id))


# ---- Subscription catalog (read-only) ----


@router.get("/subscription/plans")
def subscription_plans(
    auth: Annotated[AuthContext, Depends(require_dashboard)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.list_subscription_plans(db, _school_id(auth)))


@router.get("/subscription/addons")
def subscription_addons(
    auth: Annotated[AuthContext, Depends(require_dashboard)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.list_subscription_addons(db, _school_id(auth)))
