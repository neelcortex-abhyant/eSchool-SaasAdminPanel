"""School Admin academic management wave routes (mounted under /school-admin)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_school_permission
from app.schemas.v1 import school_admin_erp as erp_schemas
from app.schemas.v1 import school_admin_mgmt as mgmt_schemas
from app.schemas.v1 import school_admin_mgmt_responses as mgmt_out
from app.schemas.v1.school_admin_erp_responses import (
    DeletedOut,
    FeeAssignmentListOut,
    FeeAssignmentOut,
    FeeConcessionListOut,
    FeeConcessionOut,
    FeeOutstandingOut,
    FeePaymentListOut,
    FeePaymentOut,
    FeeStructureListOut,
    FeeStructureOut,
    FeeTypeListOut,
    FeeTypeOut,
    GradingScaleListOut,
    GradingScaleOut,
    ReportCardAdminOut,
    ReportCardGenerateOut,
    ReportCardListOut,
    SalaryComponentListOut,
    SalaryComponentOut,
    StudentTransportAssignmentListOut,
    StudentTransportAssignmentOut,
    TransportRouteListOut,
    TransportRouteOut,
    TransportStopListOut,
    TransportStopOut,
    VehicleListOut,
    VehicleOut,
    json_response,
)
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


def _school_id(auth: AuthContext) -> int:
    return int(auth.user.school_id)  # type: ignore[arg-type]


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def _mgmt_body(body: BaseModel) -> dict[str, Any]:
    return mgmt.sanitize_body(mgmt_schemas.dump_mgmt_body(body))


def _erp_body(body: BaseModel) -> dict[str, Any]:
    return mgmt.sanitize_body(erp_schemas.dump_erp_body(body))


# ---- Grading scales ----


@router.get("/grading-scales", responses=json_response(GradingScaleListOut))
def list_grading_scales(
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_grading_scales(db, _school_id(auth), page=page, page_size=page_size))


@router.post(
    "/grading-scales",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(GradingScaleOut, status_code=201),
)
def create_grading_scale(
    body: erp_schemas.GradingScaleCreateBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_grading_scale(db, _school_id(auth), _erp_body(body)))


@router.get("/grading-scales/{scale_id}", responses=json_response(GradingScaleOut))
def get_grading_scale(
    scale_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_grading_scale(db, _school_id(auth), scale_id))


@router.patch("/grading-scales/{scale_id}", responses=json_response(GradingScaleOut))
def patch_grading_scale(
    scale_id: int,
    body: erp_schemas.GradingScalePatchBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_grading_scale(db, _school_id(auth), scale_id, _erp_body(body)))


@router.delete("/grading-scales/{scale_id}", responses=json_response(DeletedOut))
def delete_grading_scale(
    scale_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_grading_scale(db, _school_id(auth), scale_id))


# ---- Report cards ----


@router.get("/report-cards", responses=json_response(ReportCardListOut))
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


@router.post(
    "/report-cards",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(ReportCardGenerateOut, status_code=201),
)
def generate_report_cards(
    body: erp_schemas.ReportCardGenerateBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    data = _erp_body(body)
    exam_id = int(data["exam_id"])
    scale_id = int(data["grading_scale_id"]) if data.get("grading_scale_id") is not None else None
    return _run(lambda: mgmt.generate_report_cards(db, _school_id(auth), exam_id, scale_id))


@router.get("/report-cards/{report_id}", responses=json_response(ReportCardAdminOut))
def get_report_card(
    report_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_report_card(db, _school_id(auth), report_id))


# ---- Question bank ----


@router.get("/question-bank", responses=mgmt_out.json_response(mgmt_out.QuestionBankListOut))
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


@router.post("/question-bank", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.QuestionBankOut, status_code=201))
def create_question_bank(
    body: mgmt_schemas.QuestionBankCreateBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_question_bank(db, _school_id(auth), _mgmt_body(body)))


@router.get("/question-bank/{question_id}", responses=mgmt_out.json_response(mgmt_out.QuestionBankOut))
def get_question_bank(
    question_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_question_bank(db, _school_id(auth), question_id))


@router.patch("/question-bank/{question_id}", responses=mgmt_out.json_response(mgmt_out.QuestionBankOut))
def patch_question_bank(
    question_id: int,
    body: mgmt_schemas.QuestionBankPatchBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_question_bank(db, _school_id(auth), question_id, _mgmt_body(body)))


@router.delete("/question-bank/{question_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_question_bank(
    question_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_question_bank(db, _school_id(auth), question_id))


@router.post("/online-assessments/{assessment_id}/questions/from-bank", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.CopyFromBankOut, status_code=201))
def copy_from_bank(
    assessment_id: int,
    body: mgmt_schemas.CopyFromBankBody,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
):
    ids = list(body.question_ids)
    return _run(lambda: mgmt.copy_questions_to_assessment(db, _school_id(auth), assessment_id, ids))


# ---- Admission inquiries / holidays ----


@router.get("/admission-inquiries", responses=mgmt_out.json_response(mgmt_out.AdmissionInquiryListOut))
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


@router.post("/admission-inquiries", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.AdmissionInquiryOut, status_code=201))
def create_admission_inquiry(
    body: mgmt_schemas.AdmissionInquiryCreateBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_admission_inquiry(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/admission-inquiries/{row_id}", responses=mgmt_out.json_response(mgmt_out.AdmissionInquiryOut))
def patch_admission_inquiry(
    row_id: int,
    body: mgmt_schemas.AdmissionInquiryPatchBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_admission_inquiry(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/admission-inquiries/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_admission_inquiry(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_admission_inquiry(db, _school_id(auth), row_id))


@router.get("/holidays", responses=mgmt_out.json_response(mgmt_out.HolidayListOut))
def list_holidays(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_holidays(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/holidays", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.HolidayOut, status_code=201))
def create_holiday(
    body: mgmt_schemas.HolidayCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_holiday(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/holidays/{row_id}", responses=mgmt_out.json_response(mgmt_out.HolidayOut))
def patch_holiday(
    row_id: int,
    body: mgmt_schemas.HolidayPatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_holiday(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/holidays/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_holiday(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_holiday(db, _school_id(auth), row_id))


# ---- Students extras ----


@router.post("/students/import", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.StudentsImportOut, status_code=201))
def import_students(
    body: mgmt_schemas.StudentsImportBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    rows = body.row_list()
    return _run(lambda: mgmt.bulk_import_students(db, _school_id(auth), rows))


@router.post("/students/promote", responses=mgmt_out.json_response(mgmt_out.StudentsPromoteOut))
def promote_students(
    body: mgmt_schemas.StudentsPromoteBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.promote_students(db, _school_id(auth), _mgmt_body(body)))


@router.post("/students/{student_id}/transfer", responses=mgmt_out.json_response(mgmt_out.StudentTransferOut))
def transfer_student(
    student_id: int,
    body: mgmt_schemas.StudentTransferBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.transfer_student(db, _school_id(auth), student_id, _mgmt_body(body)))


@router.post("/students/{student_id}/reset-password", responses=mgmt_out.json_response(mgmt_out.StudentPasswordResetOut))
def reset_student_password(
    student_id: int,
    body: mgmt_schemas.StudentResetPasswordBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.reset_student_password(db, _school_id(auth), student_id, _mgmt_body(body)))


@router.get("/students/{student_id}/electives", responses=mgmt_out.json_response(mgmt_out.StudentElectiveListOut))
def list_electives(
    student_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.list_student_electives(db, _school_id(auth), student_id))


@router.post("/students/{student_id}/electives", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.StudentElectiveOut, status_code=201))
def assign_elective(
    student_id: int,
    body: mgmt_schemas.StudentElectiveCreateBody,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.assign_student_elective(db, _school_id(auth), student_id, _mgmt_body(body)))


@router.delete("/students/{student_id}/electives/{elective_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def remove_elective(
    student_id: int,
    elective_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.remove_student_elective(db, _school_id(auth), student_id, elective_id))


# ---- Fees ----


@router.get("/fee-types", responses=json_response(FeeTypeListOut))
def list_fee_types(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_fee_types(db, _school_id(auth), page=page, page_size=page_size))


@router.post(
    "/fee-types",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(FeeTypeOut, status_code=201),
)
def create_fee_type(
    body: erp_schemas.FeeTypeCreateBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_fee_type(db, _school_id(auth), _erp_body(body)))


@router.patch("/fee-types/{row_id}", responses=json_response(FeeTypeOut))
def patch_fee_type(
    row_id: int,
    body: erp_schemas.FeeTypePatchBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_fee_type(db, _school_id(auth), row_id, _erp_body(body)))


@router.delete("/fee-types/{row_id}", responses=json_response(DeletedOut))
def delete_fee_type(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_fee_type(db, _school_id(auth), row_id))


@router.get("/fee-structures", responses=json_response(FeeStructureListOut))
def list_fee_structures(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_fee_structures(db, _school_id(auth), page=page, page_size=page_size))


@router.post(
    "/fee-structures",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(FeeStructureOut, status_code=201),
)
def create_fee_structure(
    body: erp_schemas.FeeStructureCreateBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_fee_structure(db, _school_id(auth), _erp_body(body)))


@router.get("/fee-structures/{row_id}", responses=json_response(FeeStructureOut))
def get_fee_structure(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_fee_structure(db, _school_id(auth), row_id))


@router.patch("/fee-structures/{row_id}", responses=json_response(FeeStructureOut))
def patch_fee_structure(
    row_id: int,
    body: erp_schemas.FeeStructurePatchBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_fee_structure(db, _school_id(auth), row_id, _erp_body(body)))


@router.delete("/fee-structures/{row_id}", responses=json_response(DeletedOut))
def delete_fee_structure(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_fee_structure(db, _school_id(auth), row_id))


@router.get("/fee-assignments", responses=json_response(FeeAssignmentListOut))
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


@router.post(
    "/fee-assignments",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(FeeAssignmentOut, status_code=201),
)
def create_fee_assignment(
    body: erp_schemas.FeeAssignmentCreateBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_fee_assignment(db, _school_id(auth), _erp_body(body)))


@router.delete("/fee-assignments/{row_id}", responses=json_response(DeletedOut))
def delete_fee_assignment(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_fee_assignment(db, _school_id(auth), row_id))


@router.get("/fee-concessions", responses=json_response(FeeConcessionListOut))
def list_fee_concessions(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_fee_concessions(db, _school_id(auth), page=page, page_size=page_size))


@router.post(
    "/fee-concessions",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(FeeConcessionOut, status_code=201),
)
def create_fee_concession(
    body: erp_schemas.FeeConcessionCreateBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_fee_concession(db, _school_id(auth), _erp_body(body)))


@router.delete("/fee-concessions/{row_id}", responses=json_response(DeletedOut))
def delete_fee_concession(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_fee_concession(db, _school_id(auth), row_id))


@router.get("/fee-payments", responses=json_response(FeePaymentListOut))
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


@router.get("/fees/outstanding", responses=json_response(FeeOutstandingOut))
def fees_outstanding(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.fees_outstanding(db, _school_id(auth), page=page, page_size=page_size))


@router.post(
    "/fees/collect",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(FeePaymentOut, status_code=201),
)
def fees_collect(
    body: erp_schemas.FeeCollectBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.collect_fee(db, _school_id(auth), _erp_body(body)))


# ---- Semesters / streams / shifts / syllabi / online classes ----


@router.get("/semesters", responses=mgmt_out.json_response(mgmt_out.SemesterListOut))
def list_semesters(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_semesters(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/semesters", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.SemesterOut, status_code=201))
def create_semester(
    body: mgmt_schemas.SemesterCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_semester(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/semesters/{row_id}", responses=mgmt_out.json_response(mgmt_out.SemesterOut))
def patch_semester(
    row_id: int,
    body: mgmt_schemas.SemesterPatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_semester(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/semesters/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_semester(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_semester(db, _school_id(auth), row_id))


@router.get("/streams", responses=mgmt_out.json_response(mgmt_out.StreamListOut))
def list_streams(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_streams(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/streams", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.StreamOut, status_code=201))
def create_stream(
    body: mgmt_schemas.StreamCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_stream(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/streams/{row_id}", responses=mgmt_out.json_response(mgmt_out.StreamOut))
def patch_stream(
    row_id: int,
    body: mgmt_schemas.StreamPatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_stream(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/streams/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_stream(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_stream(db, _school_id(auth), row_id))


@router.get("/shifts", responses=mgmt_out.json_response(mgmt_out.ShiftListOut))
def list_shifts(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_shifts(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/shifts", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.ShiftOut, status_code=201))
def create_shift(
    body: mgmt_schemas.ShiftCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_shift(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/shifts/{row_id}", responses=mgmt_out.json_response(mgmt_out.ShiftOut))
def patch_shift(
    row_id: int,
    body: mgmt_schemas.ShiftPatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_shift(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/shifts/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_shift(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_shift(db, _school_id(auth), row_id))


@router.get("/syllabi", responses=mgmt_out.json_response(mgmt_out.SyllabusListOut))
def list_syllabi(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_syllabi(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/syllabi", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.SyllabusOut, status_code=201))
def create_syllabus(
    body: mgmt_schemas.SyllabusCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_syllabus(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/syllabi/{row_id}", responses=mgmt_out.json_response(mgmt_out.SyllabusOut))
def patch_syllabus(
    row_id: int,
    body: mgmt_schemas.SyllabusPatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_syllabus(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/syllabi/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_syllabus(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_syllabus(db, _school_id(auth), row_id))


@router.get("/online-classes", responses=mgmt_out.json_response(mgmt_out.OnlineClassListOut))
def list_online_classes(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_online_classes(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/online-classes", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.OnlineClassOut, status_code=201))
def create_online_class(
    body: mgmt_schemas.OnlineClassCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_online_class(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/online-classes/{row_id}", responses=mgmt_out.json_response(mgmt_out.OnlineClassOut))
def patch_online_class(
    row_id: int,
    body: mgmt_schemas.OnlineClassPatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_online_class(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/online-classes/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_online_class(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_online_class(db, _school_id(auth), row_id))


# ---- Staff bulk upload + role permissions ----


@router.get("/staff-roles", responses=mgmt_out.json_response(mgmt_out.StaffRolesListOut))
def list_staff_roles(
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.list_staff_roles(db, _school_id(auth)))


@router.get("/staff/{user_id}/roles", responses=mgmt_out.json_response(mgmt_out.StaffUserRolesOut))
def get_staff_roles(
    user_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_staff_user_roles(db, _school_id(auth), user_id))


@router.put("/staff/{user_id}/roles", responses=mgmt_out.json_response(mgmt_out.StaffUserRolesOut))
def put_staff_roles(
    user_id: int,
    body: mgmt_schemas.StaffRolesPutBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    roles = list(body.roles)
    return _run(lambda: mgmt.set_staff_user_roles(db, _school_id(auth), user_id, roles))


@router.post("/staff/import", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.StaffImportOut, status_code=201))
def import_staff(
    body: mgmt_schemas.StaffImportBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    rows = body.row_list()
    return _run(lambda: mgmt.bulk_import_staff(db, _school_id(auth), rows))


# ---- Staff attendance / QR / tasks ----


@router.post("/staff-attendance", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.StaffAttendanceOut, status_code=201))
def mark_staff_attendance(
    body: mgmt_schemas.StaffAttendanceMarkBody,
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.mark_staff_attendance(db, _school_id(auth), _mgmt_body(body)))


@router.get("/staff-attendance/today", responses=mgmt_out.json_response(mgmt_out.StaffAttendanceTodayOut))
def staff_attendance_today(
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.staff_attendance_today(db, _school_id(auth)))


@router.get("/staff-attendance/register", responses=mgmt_out.json_response(mgmt_out.StaffAttendanceRegisterOut))
def staff_attendance_register(
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
    attendance_date: date | None = Query(None),
):
    return _run(lambda: mgmt.staff_attendance_register(db, _school_id(auth), attendance_date))


@router.get("/staff-attendance/reports", responses=mgmt_out.json_response(mgmt_out.StaffAttendanceReportOut))
def staff_attendance_reports(
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
):
    return _run(
        lambda: mgmt.staff_attendance_report(db, _school_id(auth), from_date=from_date, to_date=to_date)
    )


@router.get("/staff-qr-attendance-settings", responses=mgmt_out.json_response(mgmt_out.StaffQrSettingsOut))
def get_staff_qr_settings(
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_staff_qr_settings(db, _school_id(auth)))


@router.put("/staff-qr-attendance-settings", responses=mgmt_out.json_response(mgmt_out.StaffQrSettingsOut))
def put_staff_qr_settings(
    body: mgmt_schemas.StaffQrSettingsPutBody,
    auth: Annotated[AuthContext, Depends(require_attendance)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.put_staff_qr_settings(db, _school_id(auth), _mgmt_body(body)))


@router.get("/staff-tasks", responses=mgmt_out.json_response(mgmt_out.StaffTaskListOut))
def list_staff_tasks(
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_staff_tasks(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/staff-tasks", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.StaffTaskOut, status_code=201))
def create_staff_task(
    body: mgmt_schemas.StaffTaskCreateBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_staff_task(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/staff-tasks/{row_id}", responses=mgmt_out.json_response(mgmt_out.StaffTaskOut))
def patch_staff_task(
    row_id: int,
    body: mgmt_schemas.StaffTaskPatchBody,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_staff_task(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/staff-tasks/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_staff_task(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_staff_task(db, _school_id(auth), row_id))


# ---- Expense / income / payroll ----


@router.get("/expense-categories", responses=mgmt_out.json_response(mgmt_out.NamedCategoryListOut))
def list_expense_categories(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_expense_categories(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/expense-categories", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.NamedCategoryOut, status_code=201))
def create_expense_category(
    body: mgmt_schemas.NamedCategoryCreateBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_expense_category(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/expense-categories/{row_id}", responses=mgmt_out.json_response(mgmt_out.NamedCategoryOut))
def patch_expense_category(
    row_id: int,
    body: mgmt_schemas.NamedCategoryPatchBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_expense_category(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/expense-categories/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_expense_category(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_expense_category(db, _school_id(auth), row_id))


@router.get("/income-categories", responses=mgmt_out.json_response(mgmt_out.NamedCategoryListOut))
def list_income_categories(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_income_categories(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/income-categories", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.NamedCategoryOut, status_code=201))
def create_income_category(
    body: mgmt_schemas.NamedCategoryCreateBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_income_category(db, _school_id(auth), _mgmt_body(body)))


@router.delete("/income-categories/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_income_category(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_income_category(db, _school_id(auth), row_id))


@router.get("/incomes/dashboard", responses=mgmt_out.json_response(mgmt_out.IncomesDashboardOut))
def incomes_dashboard(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.incomes_dashboard(db, _school_id(auth)))


@router.get("/incomes", responses=mgmt_out.json_response(mgmt_out.IncomeListOut))
def list_incomes(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_incomes(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/incomes", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.IncomeOut, status_code=201))
def create_income(
    body: mgmt_schemas.IncomeCreateBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_income(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/incomes/{row_id}", responses=mgmt_out.json_response(mgmt_out.IncomeOut))
def patch_income(
    row_id: int,
    body: mgmt_schemas.IncomePatchBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_income(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/incomes/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_income(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_income(db, _school_id(auth), row_id))


@router.get("/payroll-settings", responses=mgmt_out.json_response(mgmt_out.PayrollSettingsOut))
def get_payroll_settings(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_payroll_settings(db, _school_id(auth)))


@router.put("/payroll-settings", responses=mgmt_out.json_response(mgmt_out.PayrollSettingsOut))
def put_payroll_settings(
    body: mgmt_schemas.PayrollSettingsPutBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.put_payroll_settings(db, _school_id(auth), _mgmt_body(body)))


@router.get("/payroll-runs", responses=mgmt_out.json_response(mgmt_out.PayrollRunListOut))
def list_payroll_runs(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_payroll_runs(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/payroll-runs", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.PayrollRunOut, status_code=201))
def create_payroll_run(
    body: mgmt_schemas.PayrollRunCreateBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_payroll_run(db, _school_id(auth), _mgmt_body(body)))


# ---- Salary components (payroll catalog) ----


@router.get("/salary-components", responses=json_response(SalaryComponentListOut))
def list_salary_components(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    kind: str | None = Query(default=None, description="earning|deduction"),
    active_only: bool = Query(False),
):
    return _run(
        lambda: mgmt.list_salary_components(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            kind=kind,
            active_only=active_only,
        )
    )


@router.post(
    "/salary-components",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(SalaryComponentOut, status_code=201),
)
def create_salary_component(
    body: erp_schemas.SalaryComponentCreateBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_salary_component(db, _school_id(auth), _erp_body(body)))


@router.get("/salary-components/{row_id}", responses=json_response(SalaryComponentOut))
def get_salary_component(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_salary_component(db, _school_id(auth), row_id))


@router.patch("/salary-components/{row_id}", responses=json_response(SalaryComponentOut))
def patch_salary_component(
    row_id: int,
    body: erp_schemas.SalaryComponentPatchBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_salary_component(db, _school_id(auth), row_id, _erp_body(body)))


@router.delete("/salary-components/{row_id}", responses=json_response(DeletedOut))
def delete_salary_component(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_salary_component(db, _school_id(auth), row_id))


# ---- Transport ----


@router.get("/vehicles", responses=json_response(VehicleListOut))
def list_vehicles(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_vehicles(db, _school_id(auth), page=page, page_size=page_size))


@router.post(
    "/vehicles",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(VehicleOut, status_code=201),
)
def create_vehicle(
    body: erp_schemas.VehicleCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_vehicle(db, _school_id(auth), _erp_body(body)))


@router.patch("/vehicles/{row_id}", responses=json_response(VehicleOut))
def patch_vehicle(
    row_id: int,
    body: erp_schemas.VehiclePatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_vehicle(db, _school_id(auth), row_id, _erp_body(body)))


@router.delete("/vehicles/{row_id}", responses=json_response(DeletedOut))
def delete_vehicle(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_vehicle(db, _school_id(auth), row_id))


@router.get("/transport-routes", responses=json_response(TransportRouteListOut))
def list_transport_routes(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_transport_routes(db, _school_id(auth), page=page, page_size=page_size))


@router.post(
    "/transport-routes",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(TransportRouteOut, status_code=201),
)
def create_transport_route(
    body: erp_schemas.TransportRouteCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_transport_route(db, _school_id(auth), _erp_body(body)))


@router.patch("/transport-routes/{row_id}", responses=json_response(TransportRouteOut))
def patch_transport_route(
    row_id: int,
    body: erp_schemas.TransportRoutePatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_transport_route(db, _school_id(auth), row_id, _erp_body(body)))


@router.delete("/transport-routes/{row_id}", responses=json_response(DeletedOut))
def delete_transport_route(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_transport_route(db, _school_id(auth), row_id))


@router.get("/transport-stops", responses=json_response(TransportStopListOut))
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


@router.post(
    "/transport-stops",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(TransportStopOut, status_code=201),
)
def create_transport_stop(
    body: erp_schemas.TransportStopCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_transport_stop(db, _school_id(auth), _erp_body(body)))


@router.delete("/transport-stops/{row_id}", responses=json_response(DeletedOut))
def delete_transport_stop(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_transport_stop(db, _school_id(auth), row_id))


@router.get(
    "/student-transport-assignments",
    responses=json_response(StudentTransportAssignmentListOut),
)
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


@router.post(
    "/student-transport-assignments",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(StudentTransportAssignmentOut, status_code=201),
)
def create_student_transport_assignment(
    body: erp_schemas.StudentTransportAssignmentCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: mgmt.create_student_transport_assignment(db, _school_id(auth), _erp_body(body))
    )


@router.delete(
    "/student-transport-assignments/{row_id}",
    responses=json_response(DeletedOut),
)
def delete_student_transport_assignment(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_student_transport_assignment(db, _school_id(auth), row_id))


# ---- Certificates / ID cards ----


@router.get("/certificate-templates", responses=mgmt_out.json_response(mgmt_out.CertificateTemplateListOut))
def list_certificate_templates(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(
        lambda: mgmt.list_certificate_templates(db, _school_id(auth), page=page, page_size=page_size)
    )


@router.post("/certificate-templates", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.CertificateTemplateOut, status_code=201))
def create_certificate_template(
    body: mgmt_schemas.CertificateTemplateCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_certificate_template(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/certificate-templates/{row_id}", responses=mgmt_out.json_response(mgmt_out.CertificateTemplateOut))
def patch_certificate_template(
    row_id: int,
    body: mgmt_schemas.CertificateTemplatePatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_certificate_template(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/certificate-templates/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_certificate_template(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_certificate_template(db, _school_id(auth), row_id))


@router.post("/certificates/issue", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.CertificateIssueOut, status_code=201))
def issue_certificate(
    body: mgmt_schemas.CertificateIssueBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.issue_certificate(db, _school_id(auth), _mgmt_body(body)))


@router.get("/id-card-settings", responses=mgmt_out.json_response(mgmt_out.IdCardSettingsOut))
def get_id_card_settings(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.get_id_card_settings(db, _school_id(auth)))


@router.put("/id-card-settings", responses=mgmt_out.json_response(mgmt_out.IdCardSettingsOut))
def put_id_card_settings(
    body: mgmt_schemas.IdCardSettingsPutBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.put_id_card_settings(db, _school_id(auth), _mgmt_body(body)))


@router.get("/students/{student_id}/id-card", responses=mgmt_out.json_response(mgmt_out.StudentIdCardOut))
def student_id_card(
    student_id: int,
    auth: Annotated[AuthContext, Depends(require_students)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.student_id_card_payload(db, _school_id(auth), student_id))


@router.get("/staff/{staff_id}/id-card", responses=mgmt_out.json_response(mgmt_out.StaffIdCardOut))
def staff_id_card(
    staff_id: int,
    auth: Annotated[AuthContext, Depends(require_staff)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.staff_id_card_payload(db, _school_id(auth), staff_id))


# ---- Reports ----


@router.get("/reports/students", responses=mgmt_out.json_response(mgmt_out.ReportStudentsOut))
def reports_students(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_students(db, _school_id(auth)))


@router.get("/reports/teachers", responses=mgmt_out.json_response(mgmt_out.ReportTeachersOut))
def reports_teachers(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_teachers(db, _school_id(auth)))


@router.get("/reports/staff", responses=mgmt_out.json_response(mgmt_out.ReportStaffOut))
def reports_staff(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_staff(db, _school_id(auth)))


@router.get("/reports/exams", responses=mgmt_out.json_response(mgmt_out.ReportExamsOut))
def reports_exams(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_exams(db, _school_id(auth)))


@router.get("/reports/expenses", responses=mgmt_out.json_response(mgmt_out.ReportAmountCountOut))
def reports_expenses(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_expenses(db, _school_id(auth)))


@router.get("/reports/income", responses=mgmt_out.json_response(mgmt_out.ReportAmountCountOut))
def reports_income(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_income(db, _school_id(auth)))


@router.get("/reports/financial-summary", responses=mgmt_out.json_response(mgmt_out.ReportFinancialSummaryOut))
def reports_financial_summary(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.report_financial_summary(db, _school_id(auth)))


# ---- Diary / notifications / announcements / sliders / gallery ----


@router.get("/diary-categories", responses=mgmt_out.json_response(mgmt_out.DiaryCategoryListOut))
def list_diary_categories(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_diary_categories(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/diary-categories", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.DiaryCategoryOut, status_code=201))
def create_diary_category(
    body: mgmt_schemas.DiaryCategoryCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_diary_category(db, _school_id(auth), _mgmt_body(body)))


@router.delete("/diary-categories/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_diary_category(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_diary_category(db, _school_id(auth), row_id))


@router.get("/student-diaries", responses=mgmt_out.json_response(mgmt_out.StudentDiaryListOut))
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


@router.post("/student-diaries", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.StudentDiaryOut, status_code=201))
def create_student_diary(
    body: mgmt_schemas.StudentDiaryCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_student_diary(db, _school_id(auth), _mgmt_body(body)))


@router.delete("/student-diaries/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_student_diary(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_student_diary(db, _school_id(auth), row_id))


@router.get("/notifications", responses=mgmt_out.json_response(mgmt_out.NotificationListOut))
def list_notifications(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_notifications(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/notifications", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.NotificationOut, status_code=201))
def create_notification(
    body: mgmt_schemas.NotificationCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: mgmt.create_notification(
            db, _school_id(auth), _mgmt_body(body), created_by=str(auth.user.id)
        )
    )


@router.get("/announcements", responses=mgmt_out.json_response(mgmt_out.AnnouncementListOut))
def list_announcements(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_announcements(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/announcements", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.AnnouncementOut, status_code=201))
def create_announcement(
    body: mgmt_schemas.AnnouncementCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_announcement(db, _school_id(auth), _mgmt_body(body)))


@router.get("/sliders", responses=mgmt_out.json_response(mgmt_out.SliderListOut))
def list_sliders(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_sliders(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/sliders", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.SliderOut, status_code=201))
def create_slider(
    body: mgmt_schemas.SliderCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_slider(db, _school_id(auth), _mgmt_body(body)))


@router.patch("/sliders/{row_id}", responses=mgmt_out.json_response(mgmt_out.SliderOut))
def patch_slider(
    row_id: int,
    body: mgmt_schemas.SliderPatchBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.update_slider(db, _school_id(auth), row_id, _mgmt_body(body)))


@router.delete("/sliders/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_slider(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_slider(db, _school_id(auth), row_id))


@router.get("/gallery", responses=mgmt_out.json_response(mgmt_out.GalleryListOut))
def list_gallery(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(lambda: mgmt.list_gallery(db, _school_id(auth), page=page, page_size=page_size))


@router.post("/gallery", status_code=status.HTTP_201_CREATED, responses=mgmt_out.json_response(mgmt_out.GalleryItemOut, status_code=201))
def create_gallery_item(
    body: mgmt_schemas.GalleryCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.create_gallery_item(db, _school_id(auth), _mgmt_body(body)))


@router.delete("/gallery/{row_id}", responses=mgmt_out.json_response(mgmt_out.DeletedOut))
def delete_gallery_item(
    row_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.soft_delete_gallery_item(db, _school_id(auth), row_id))


# ---- Subscription catalog (read-only) ----


@router.get("/subscription/plans", responses=mgmt_out.json_response(mgmt_out.SubscriptionPlansOut))
def subscription_plans(
    auth: Annotated[AuthContext, Depends(require_dashboard)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.list_subscription_plans(db, _school_id(auth)))


@router.get("/subscription/addons", responses=mgmt_out.json_response(mgmt_out.SubscriptionAddonsOut))
def subscription_addons(
    auth: Annotated[AuthContext, Depends(require_dashboard)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: mgmt.list_subscription_addons(db, _school_id(auth)))
