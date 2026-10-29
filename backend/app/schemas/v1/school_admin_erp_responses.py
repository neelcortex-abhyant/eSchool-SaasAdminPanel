"""OpenAPI response models for School Admin ERP modules 1–5.

Derived from actual service return dicts. Used via FastAPI ``responses={code: {"model": ...}}``
so documentation is accurate without changing runtime serialization/validation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(extra="ignore")


class DeletedOut(_Out):
    id: int
    deleted: bool = True


class PageMeta(_Out):
    items: list[Any]
    total: int
    page: int
    page_size: int


# ---- M1 grading / report cards ----


class GradingScaleBandOut(_Out):
    id: int
    letter: str
    min_percent: float
    max_percent: float
    grade_point: float | None = None
    remark: str | None = None
    is_pass: int
    sort_order: int


class GradingScaleOut(_Out):
    id: int
    school_id: int
    name: str
    description: str | None = None
    is_default: int
    status: int
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    bands: list[GradingScaleBandOut] = Field(default_factory=list)


class GradingScaleListOut(_Out):
    items: list[GradingScaleOut]
    total: int
    page: int
    page_size: int


class ReportCardAdminOut(_Out):
    id: int
    school_id: int
    exam_id: int
    student_id: int
    grading_scale_id: int | None = None
    percentage: float
    letter_grade: str | None = None
    passed: int
    subjects_json: str | None = None
    generated_at: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ReportCardListOut(_Out):
    items: list[ReportCardAdminOut]
    total: int
    page: int
    page_size: int


class ReportCardGenerateOut(_Out):
    exam_id: int
    created: int
    items: list[ReportCardAdminOut]
    total: int


class ReportCardPortalOut(_Out):
    id: int
    school_id: int
    exam_id: int
    exam_name: str | None = None
    student_id: int
    student_name: str | None = None
    grading_scale_id: int | None = None
    percentage: float
    letter_grade: str | None = None
    passed: int
    subjects: Any = None
    generated_at: str | None = None


class ReportCardPortalListOut(_Out):
    items: list[ReportCardPortalOut]
    total: int


# ---- M2 fees structures ----


class FeeTypeOut(_Out):
    id: int
    school_id: int
    name: str
    category: str
    description: str | None = None
    status: int
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class FeeTypeListOut(_Out):
    items: list[FeeTypeOut]
    total: int
    page: int
    page_size: int


class FeeStructureAmountOut(_Out):
    id: int
    school_id: int
    structure_id: int
    fee_type_id: int
    amount: float
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class FeeStructureOut(_Out):
    id: int
    school_id: int
    name: str
    session_year_id: int
    class_id: int | None = None
    status: int
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    amounts: list[FeeStructureAmountOut] = Field(default_factory=list)
    total: float = 0
    installments: list[FeeInstallmentOut] = Field(default_factory=list)


class FeeStructureListOut(_Out):
    items: list[FeeStructureOut]
    total: int
    page: int
    page_size: int


class FeeInstallmentOut(_Out):
    id: int
    structure_id: int
    name: str
    due_date: str
    amount: float
    sort_order: int
    allocated: float
    outstanding: float


class FeeInstallmentListOut(_Out):
    items: list[FeeInstallmentOut]
    total: int


class FeeAssignmentOut(_Out):
    id: int
    school_id: int
    structure_id: int
    student_id: int
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class FeeAssignmentListOut(_Out):
    items: list[FeeAssignmentOut]
    total: int
    page: int
    page_size: int


class FeeConcessionOut(_Out):
    id: int
    school_id: int
    student_id: int
    structure_id: int
    kind: str
    value: float
    reason: str
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class FeeConcessionListOut(_Out):
    items: list[FeeConcessionOut]
    total: int
    page: int
    page_size: int


# ---- M3 collection ----


class FeePaymentOut(_Out):
    id: int
    school_id: int
    assignment_id: int
    student_id: int
    amount: float
    method: str
    receipt_no: str | None = None
    reference: str | None = None
    remarks: str | None = None
    paid_on: str | None = None
    status: str
    idempotency_key: str | None = None
    cancelled_at: str | None = None
    cancel_reason: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class FeePaymentListOut(_Out):
    items: list[FeePaymentOut]
    total: int
    page: int
    page_size: int


class FeeReceiptLineOut(_Out):
    allocation_id: int
    installment_id: int | None = None
    installment_name: str | None = None
    amount: float


class FeeReceiptOut(_Out):
    id: int
    receipt_no: str | None = None
    student_id: int
    student_name: str | None = None
    assignment_id: int
    amount: float
    method: str | None = None
    reference: str | None = None
    remarks: str | None = None
    paid_on: str | None = None
    status: str
    cancelled_at: str | None = None
    cancel_reason: str | None = None
    lines: list[FeeReceiptLineOut] = Field(default_factory=list)


class FeeOutstandingItemOut(_Out):
    assignment_id: int
    student_id: int
    structure_id: int
    payable: float
    concession: float
    paid: float
    balance: float


class FeeOutstandingSummaryOut(_Out):
    payable: float
    collected: float
    outstanding: float


class FeeOutstandingOut(_Out):
    items: list[FeeOutstandingItemOut]
    total: int
    page: int
    page_size: int
    summary: FeeOutstandingSummaryOut


class FeeCollectionReportItemOut(_Out):
    id: int
    receipt_no: str | None = None
    student_id: int
    amount: float
    method: str
    paid_on: str


class FeeCollectionReportOut(_Out):
    from_date: str
    to_date: str
    class_id: int | None = None
    payment_count: int
    total_collected: float
    by_method: dict[str, float]
    items: list[FeeCollectionReportItemOut]


class FeeBalanceInstallmentOut(_Out):
    id: int
    name: str
    due_date: str
    amount: float
    allocated: float
    outstanding: float


class FeeBalanceAssignmentOut(_Out):
    assignment_id: int
    structure_id: int
    payable: float
    paid: float
    outstanding: float
    installments: list[FeeBalanceInstallmentOut] = Field(default_factory=list)


class FeeBalanceOut(_Out):
    student_id: int
    payable: float
    paid: float
    outstanding: float
    assignments: list[FeeBalanceAssignmentOut] = Field(default_factory=list)


class PortalFeePaymentItemOut(_Out):
    id: int
    receipt_no: str | None = None
    amount: float
    method: str | None = None
    paid_on: str | None = None
    status: str


class PortalFeePaymentListOut(_Out):
    items: list[PortalFeePaymentItemOut]
    total: int


# ---- M4 transport master ----


class VehicleOut(_Out):
    id: int
    school_id: int
    name: str
    registration_no: str
    capacity: int | None = None
    driver_staff_id: int | None = None
    helper_staff_id: int | None = None
    status: int
    created_at: str | None = None
    updated_at: str | None = None


class VehicleListOut(_Out):
    items: list[VehicleOut]
    total: int
    page: int
    page_size: int


class TransportStopOut(_Out):
    id: int
    school_id: int
    route_id: int
    name: str
    stop_order: int
    pickup_time: str | None = None
    drop_time: str | None = None
    landmark: str | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TransportRouteOut(_Out):
    id: int
    school_id: int
    name: str
    vehicle_id: int | None = None
    description: str | None = None
    status: int
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    stops: list[TransportStopOut] = Field(default_factory=list)


class TransportRouteListOut(_Out):
    items: list[TransportRouteOut]
    total: int
    page: int
    page_size: int


class TransportStopListOut(_Out):
    items: list[TransportStopOut]
    total: int
    page: int
    page_size: int


class StudentTransportAssignmentOut(_Out):
    id: int
    school_id: int
    student_id: int
    route_id: int
    stop_id: int | None = None
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class StudentTransportAssignmentListOut(_Out):
    items: list[StudentTransportAssignmentOut]
    total: int
    page: int
    page_size: int


# ---- M5 trips / GPS / attendance ----


class TransportTripOut(_Out):
    id: int
    school_id: int
    route_id: int
    vehicle_id: int
    driver_staff_id: int | None = None
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class TransportTripListOut(_Out):
    items: list[TransportTripOut]
    total: int
    page: int
    page_size: int


class TransportTripReportItemOut(TransportTripOut):
    gps_points: int = 0
    attendance_events: int = 0


class TransportTripReportOut(_Out):
    items: list[TransportTripReportItemOut]
    total: int
    page: int
    page_size: int


class TransportGpsPointOut(_Out):
    id: int
    trip_id: int
    vehicle_id: int
    lat: float
    lng: float
    recorded_at: str
    staff_id: int | None = None
    expires_at: str | None = None


class TransportAttendanceEventOut(_Out):
    id: int
    trip_id: int
    student_id: int
    stop_id: int | None = None
    event_type: str
    recorded_at: str


class TransportAttendanceListOut(_Out):
    items: list[TransportAttendanceEventOut]
    total: int


class ParentTransportAssignmentOut(_Out):
    id: int
    route_id: int
    route_name: str | None = None
    stop_id: int | None = None
    vehicle_id: int | None = None


class ParentTransportLiveGpsOut(_Out):
    lat: float
    lng: float
    recorded_at: str


class ParentTransportLiveOut(_Out):
    student_id: int
    assignment: ParentTransportAssignmentOut | None = None
    active_trip: TransportTripOut | None = None
    latest_gps: ParentTransportLiveGpsOut | None = None


class SalaryComponentOut(_Out):
    id: int
    school_id: int
    name: str
    code: str | None = None
    kind: str
    calc_type: str
    default_value: float
    is_active: int
    sort_order: int
    deleted_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SalaryComponentListOut(_Out):
    items: list[SalaryComponentOut]
    total: int
    page: int
    page_size: int


def json_response(model: type[BaseModel], *, status_code: int = 200) -> dict:
    """Document JSON body without enforcing response_model validation at runtime."""
    return {
        status_code: {"model": model, "description": "Successful Response"},
        404: {"description": "Record not found"},
        422: {"description": "Validation Error"},
    }
