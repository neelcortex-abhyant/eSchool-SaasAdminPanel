"""Student and parent ERP reads: report cards, fees, transport live poll."""

from __future__ import annotations

from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import require_guardian_user, require_student_user
from app.models.tables import School, Student, User
from app.schemas.v1.school_admin_erp_responses import (
    FeeBalanceOut,
    ParentTransportLiveOut,
    PortalFeePaymentListOut,
    ReportCardPortalListOut,
    ReportCardPortalOut,
    json_response,
)
from app.services.v1 import school_erp_fees as erp_fees
from app.services.v1 import school_erp_report_cards as erp_rc
from app.services.v1 import school_erp_transport as erp_transport
from app.services.v1.school_academics import AcademicError

router = APIRouter(tags=["student-erp"])

_PDF_RESPONSE = {
    200: {
        "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        "description": "PDF file",
    },
    404: {"description": "Record not found"},
}


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def _pdf_response(payload: bytes, filename: str) -> Response:
    return Response(
        content=payload,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def _student_id_for_user(db: Session, user: User, school_id: int) -> int:
    student = (
        db.query(Student)
        .filter(
            Student.user_id == user.id,
            Student.school_id == school_id,
            Student.deleted_at.is_(None),
        )
        .first()
    )
    if student is None:
        raise AcademicError(404, "Student profile not found")
    return student.id


# ---- Report cards ----


@router.get("/student/report-cards", responses=json_response(ReportCardPortalListOut))
def student_list_report_cards(
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(lambda: erp_rc.list_report_cards_for_student(db, school.id, user))


@router.get("/student/report-cards/{report_id}", responses=json_response(ReportCardPortalOut))
def student_get_report_card(
    report_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(lambda: erp_rc.get_report_card_for_portal(db, school.id, user, report_id=report_id))


@router.get("/student/report-cards/{report_id}/pdf", responses=_PDF_RESPONSE)
def student_report_card_pdf(
    report_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    payload = _run(lambda: erp_rc.render_portal_report_card_pdf(db, school.id, user, report_id))
    return _pdf_response(payload, f"report-card-{report_id}.pdf")


@router.get(
    "/parent/children/{student_id}/report-cards",
    responses=json_response(ReportCardPortalListOut),
)
def parent_list_child_report_cards(
    student_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_guardian_user),
):
    db, user, school = tenant
    return _run(lambda: erp_rc.list_report_cards_for_child(db, school.id, user, student_id))


@router.get(
    "/parent/children/{student_id}/report-cards/{report_id}",
    responses=json_response(ReportCardPortalOut),
)
def parent_get_child_report_card(
    student_id: int,
    report_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_guardian_user),
):
    db, user, school = tenant

    def _action():
        data = erp_rc.get_report_card_for_portal(db, school.id, user, report_id=report_id)
        if int(data["student_id"]) != int(student_id):
            raise AcademicError(404, "Record not found")
        return data

    return _run(_action)


@router.get("/parent/children/{student_id}/report-cards/{report_id}/pdf", responses=_PDF_RESPONSE)
def parent_child_report_card_pdf(
    student_id: int,
    report_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_guardian_user),
):
    db, user, school = tenant

    def _action():
        data = erp_rc.get_report_card_for_portal(db, school.id, user, report_id=report_id)
        if int(data["student_id"]) != int(student_id):
            raise AcademicError(404, "Record not found")
        return erp_rc.render_report_card_pdf(db, school.id, report_id)

    payload = _run(_action)
    return _pdf_response(payload, f"report-card-{report_id}.pdf")


# ---- Fees ----


@router.get("/student/fees/balance", responses=json_response(FeeBalanceOut))
def student_fee_balance(
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    return _run(lambda: erp_fees.portal_student_fee_balance(db, school.id, user))


@router.get("/student/fees/payments", responses=json_response(PortalFeePaymentListOut))
def student_fee_payments(
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant

    def _action():
        sid = _student_id_for_user(db, user, school.id)
        return erp_fees.portal_list_payments(db, school.id, user, sid)

    return _run(_action)


@router.get("/student/fees/payments/{payment_id}/receipt/pdf", responses=_PDF_RESPONSE)
def student_fee_receipt_pdf(
    payment_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_student_user),
):
    db, user, school = tenant
    payload = _run(lambda: erp_fees.portal_payment_receipt_pdf(db, school.id, user, payment_id))
    return _pdf_response(payload, f"fee-receipt-{payment_id}.pdf")


@router.get(
    "/parent/children/{student_id}/fees/balance",
    responses=json_response(FeeBalanceOut),
)
def parent_child_fee_balance(
    student_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_guardian_user),
):
    db, user, school = tenant
    return _run(lambda: erp_fees.portal_child_fee_balance(db, school.id, user, student_id))


@router.get(
    "/parent/children/{student_id}/fees/payments",
    responses=json_response(PortalFeePaymentListOut),
)
def parent_child_fee_payments(
    student_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_guardian_user),
):
    db, user, school = tenant
    return _run(lambda: erp_fees.portal_list_payments(db, school.id, user, student_id))


@router.get(
    "/parent/children/{student_id}/fees/payments/{payment_id}/receipt/pdf",
    responses=_PDF_RESPONSE,
)
def parent_child_fee_receipt_pdf(
    student_id: int,
    payment_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_guardian_user),
):
    db, user, school = tenant

    def _action():
        receipt = erp_fees.get_payment_receipt(db, school.id, payment_id)
        if int(receipt["student_id"]) != int(student_id):
            raise AcademicError(404, "Record not found")
        return erp_fees.portal_payment_receipt_pdf(db, school.id, user, payment_id)

    payload = _run(_action)
    return _pdf_response(payload, f"fee-receipt-{payment_id}.pdf")


# ---- Transport live (HTTP poll) ----


@router.get(
    "/parent/children/{student_id}/transport/live",
    responses=json_response(ParentTransportLiveOut),
)
def parent_child_transport_live(
    student_id: int,
    tenant: Tuple[Session, User, School] = Depends(require_guardian_user),
):
    db, user, school = tenant
    return _run(lambda: erp_transport.parent_child_bus_status(db, school.id, user, student_id))
