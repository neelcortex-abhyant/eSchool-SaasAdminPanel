"""School Admin ERP routes (report PDF, fee installments/cancel, transport trips)."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import central_db
from app.api.v1.deps import AuthContext, require_school_permission
from app.schemas.v1 import school_admin_erp as erp_schemas
from app.schemas.v1.school_admin_erp_responses import (
    FeeCollectionReportOut,
    FeeInstallmentListOut,
    FeeReceiptOut,
    TransportAttendanceEventOut,
    TransportAttendanceListOut,
    TransportGpsPointOut,
    TransportTripListOut,
    TransportTripOut,
    TransportTripReportOut,
    VehicleLocationsOut,
    json_response,
)
from app.services.v1 import rbac
from app.services.v1 import school_erp_fees as erp_fees
from app.services.v1 import school_erp_report_cards as erp_rc
from app.services.v1 import school_erp_transport as erp_transport
from app.services.v1.school_academic_mgmt import sanitize_body
from app.services.v1.school_academics import AcademicError

router = APIRouter(prefix="")

require_exams = require_school_permission(rbac.PERM_EXAMS)
require_fees = require_school_permission(rbac.PERM_FEES)
require_school = require_school_permission(rbac.PERM_SCHOOL)
require_reports = require_school_permission(rbac.PERM_REPORTS)

_PDF_RESPONSE = {
    200: {
        "content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}},
        "description": "PDF file",
    },
    404: {"description": "Record not found"},
    422: {"description": "Validation Error"},
}


def _school_id(auth: AuthContext) -> int:
    return int(auth.user.school_id)  # type: ignore[arg-type]


def _run(action):
    try:
        return action()
    except AcademicError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


def _erp_body(body: BaseModel) -> dict[str, Any]:
    return sanitize_body(erp_schemas.dump_erp_body(body))


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


@router.get("/report-cards/{report_id}/pdf", responses=_PDF_RESPONSE, response_class=Response)
def report_card_pdf(
    report_id: int,
    auth: Annotated[AuthContext, Depends(require_exams)],
    db: Annotated[Session, Depends(central_db)],
) -> Response:
    payload = _run(lambda: erp_rc.render_report_card_pdf(db, _school_id(auth), report_id))
    return _pdf_response(payload, f"report-card-{report_id}.pdf")


@router.get(
    "/fee-structures/{structure_id}/installments",
    responses=json_response(FeeInstallmentListOut),
)
def get_fee_structure_installments(
    structure_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: erp_fees.list_installments(db, _school_id(auth), structure_id))


@router.put(
    "/fee-structures/{structure_id}/installments",
    responses=json_response(FeeInstallmentListOut),
)
def put_fee_structure_installments(
    structure_id: int,
    body: erp_schemas.FeeInstallmentsPutBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    items = body.installment_rows()
    return _run(lambda: erp_fees.set_structure_installments(db, _school_id(auth), structure_id, items))


@router.get("/fee-payments/{payment_id}/receipt", responses=json_response(FeeReceiptOut))
def fee_payment_receipt(
    payment_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: erp_fees.get_payment_receipt(db, _school_id(auth), payment_id))


@router.get("/fee-payments/{payment_id}/receipt/pdf", responses=_PDF_RESPONSE, response_class=Response)
def fee_payment_receipt_pdf(
    payment_id: int,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
) -> Response:
    payload = _run(lambda: erp_fees.render_fee_receipt_pdf(db, _school_id(auth), payment_id))
    return _pdf_response(payload, f"fee-receipt-{payment_id}.pdf")


@router.post("/fee-payments/{payment_id}/cancel", responses=json_response(FeeReceiptOut))
def cancel_fee_payment(
    payment_id: int,
    body: erp_schemas.FeePaymentCancelBody,
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: erp_fees.cancel_fee_payment(
            db, _school_id(auth), payment_id, body.reason, actor=auth.user
        )
    )


@router.get("/fees/collection-report", responses=json_response(FeeCollectionReportOut))
def fees_collection_report(
    auth: Annotated[AuthContext, Depends(require_fees)],
    db: Annotated[Session, Depends(central_db)],
    from_date: date = Query(...),
    to_date: date = Query(...),
    class_id: int | None = Query(None, ge=1),
):
    return _run(
        lambda: erp_fees.fee_collection_report(
            db, _school_id(auth), from_date, to_date, class_id=class_id
        )
    )


@router.get("/transport/vehicle-locations", responses=json_response(VehicleLocationsOut))
def transport_vehicle_locations(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    """Latest GPS per in-progress vehicle for School Admin map polling."""
    return _run(lambda: erp_transport.list_vehicle_locations(db, _school_id(auth)))


@router.get("/transport-trips", responses=json_response(TransportTripListOut))
def list_transport_trips(
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    status_filter: str | None = Query(None, alias="status"),
    route_id: int | None = Query(None, ge=1),
):
    return _run(
        lambda: erp_transport.list_trips(
            db,
            _school_id(auth),
            page=page,
            page_size=page_size,
            status=status_filter,
            route_id=route_id,
        )
    )


@router.get("/transport-trips/{trip_id}", responses=json_response(TransportTripOut))
def get_transport_trip(
    trip_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: erp_transport.get_trip(db, _school_id(auth), trip_id))


@router.post(
    "/transport-trips",
    status_code=status.HTTP_201_CREATED,
    responses=json_response(TransportTripOut, status_code=201),
)
def create_transport_trip(
    body: erp_schemas.TransportTripCreateBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: erp_transport.create_trip(db, _school_id(auth), _erp_body(body)))


@router.post("/transport-trips/{trip_id}/start", responses=json_response(TransportTripOut))
def start_transport_trip(
    trip_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: erp_transport.start_trip(db, _school_id(auth), trip_id))


@router.post("/transport-trips/{trip_id}/complete", responses=json_response(TransportTripOut))
def complete_transport_trip(
    trip_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: erp_transport.complete_trip(db, _school_id(auth), trip_id))


@router.post("/transport-trips/{trip_id}/gps", responses=json_response(TransportGpsPointOut))
def post_transport_trip_gps(
    trip_id: int,
    body: erp_schemas.TransportGpsBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: erp_transport.post_gps(db, _school_id(auth), trip_id, body.lat, body.lng)
    )


@router.post(
    "/transport-trips/{trip_id}/attendance",
    responses=json_response(TransportAttendanceEventOut),
)
def post_transport_trip_attendance(
    trip_id: int,
    body: erp_schemas.TransportAttendanceBody,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(
        lambda: erp_transport.post_attendance(
            db,
            _school_id(auth),
            trip_id,
            student_id=body.student_id,
            event_type=body.event_type,
            stop_id=body.stop_id,
        )
    )


@router.get(
    "/transport-trips/{trip_id}/attendance",
    responses=json_response(TransportAttendanceListOut),
)
def get_transport_trip_attendance(
    trip_id: int,
    auth: Annotated[AuthContext, Depends(require_school)],
    db: Annotated[Session, Depends(central_db)],
):
    return _run(lambda: erp_transport.list_trip_attendance(db, _school_id(auth), trip_id))


@router.get("/transport/reports/trips", responses=json_response(TransportTripReportOut))
def transport_trips_report(
    auth: Annotated[AuthContext, Depends(require_reports)],
    db: Annotated[Session, Depends(central_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
):
    return _run(
        lambda: erp_transport.trips_report(db, _school_id(auth), page=page, page_size=page_size)
    )
