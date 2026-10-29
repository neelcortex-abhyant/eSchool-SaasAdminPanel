"""Request body schemas for School Admin ERP modules 1–5 (OpenAPI-accurate).

Fields mirror service validation in school_academic_mgmt / school_erp_* — no invented fields.
Unknown keys are ignored so clients sending extras are not broken.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _ErpBase(BaseModel):
    model_config = ConfigDict(extra="ignore")


# ---- Module 1: grading / report cards ----


class GradingScaleBandIn(_ErpBase):
    letter: str | None = Field(default=None, description="Grade letter (alias: grade)")
    grade: str | None = Field(default=None, description="Alias for letter")
    min_percent: float
    max_percent: float
    grade_point: float | None = None
    remark: str | None = Field(default=None, max_length=255)
    is_pass: bool | int | str | None = True
    sort_order: int | None = None


class GradingScaleCreateBody(_ErpBase):
    name: str = Field(..., min_length=1)
    description: str | None = None
    is_default: bool | int | str | None = False
    status: int = 1
    bands: list[GradingScaleBandIn] | None = None
    ranges: list[GradingScaleBandIn] | None = Field(
        default=None, description="Alias for bands"
    )

    @model_validator(mode="after")
    def _require_bands(self) -> GradingScaleCreateBody:
        if not (self.bands or self.ranges):
            raise ValueError("bands (or ranges) must be a non-empty list")
        return self


class GradingScalePatchBody(_ErpBase):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    is_default: bool | int | str | None = None
    status: int | None = None
    bands: list[GradingScaleBandIn] | None = None
    ranges: list[GradingScaleBandIn] | None = None


class ReportCardGenerateBody(_ErpBase):
    exam_id: int = Field(..., ge=1)
    grading_scale_id: int | None = Field(default=None, ge=1)


# ---- Module 2: fee structures ----


class FeeTypeCreateBody(_ErpBase):
    name: str = Field(..., min_length=1)
    category: str = "other"
    description: str | None = None
    status: int = 1


class FeeTypePatchBody(_ErpBase):
    name: str | None = Field(default=None, min_length=1)
    category: str | None = None
    description: str | None = None
    status: int | None = None


class FeeStructureAmountIn(_ErpBase):
    fee_type_id: int = Field(..., ge=1)
    amount: float = Field(..., gt=0)


class FeeInstallmentIn(_ErpBase):
    name: str = Field(..., min_length=1)
    due_date: date
    amount: float = Field(..., gt=0)
    sort_order: int | None = None


class FeeStructureCreateBody(_ErpBase):
    name: str = Field(..., min_length=1)
    session_year_id: int = Field(..., ge=1)
    class_id: int | None = Field(default=None, ge=1)
    status: int = 1
    amounts: list[FeeStructureAmountIn] | None = None
    items: list[FeeStructureAmountIn] | None = Field(
        default=None, description="Alias for amounts"
    )
    installments: list[FeeInstallmentIn] | None = None

    @model_validator(mode="after")
    def _require_amounts(self) -> FeeStructureCreateBody:
        if not (self.amounts or self.items):
            raise ValueError("amounts (or items) must be a non-empty list")
        return self


class FeeStructurePatchBody(_ErpBase):
    name: str | None = Field(default=None, min_length=1)
    status: int | None = None
    amounts: list[FeeStructureAmountIn] | None = None
    items: list[FeeStructureAmountIn] | None = None
    installments: list[FeeInstallmentIn] | None = None


class FeeInstallmentsPutBody(_ErpBase):
    installments: list[FeeInstallmentIn] | None = None
    items: list[FeeInstallmentIn] | None = Field(
        default=None, description="Alias for installments"
    )

    @model_validator(mode="after")
    def _require_list(self) -> FeeInstallmentsPutBody:
        if self.installments is None and self.items is None:
            raise ValueError("installments (or items) is required")
        return self

    def installment_rows(self) -> list[dict[str, Any]]:
        rows = self.installments if self.installments is not None else self.items
        return [r.model_dump(exclude_unset=True) for r in (rows or [])]


class FeeAssignmentCreateBody(_ErpBase):
    structure_id: int = Field(..., ge=1)
    student_id: int = Field(..., ge=1)


class FeeConcessionCreateBody(_ErpBase):
    student_id: int = Field(..., ge=1)
    structure_id: int = Field(..., ge=1)
    kind: Literal["percent", "amount"]
    value: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1)


# ---- Module 3: fee collection ----


class FeeCollectBody(_ErpBase):
    assignment_id: int = Field(..., ge=1)
    amount: float = Field(..., gt=0)
    method: str = "cash"
    receipt_no: str | None = None
    reference: str | None = None
    remarks: str | None = None
    paid_on: date | None = None
    idempotency_key: str | None = None


class FeePaymentCancelBody(_ErpBase):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(..., min_length=1, max_length=512)


# ---- Module 4: transport master ----


class VehicleCreateBody(_ErpBase):
    name: str = Field(..., min_length=1)
    registration_no: str = Field(..., min_length=1)
    capacity: int | None = Field(default=None, ge=1)
    status: int = 1
    driver_staff_id: int | None = Field(default=None, ge=1)
    helper_staff_id: int | None = Field(default=None, ge=1)


class VehiclePatchBody(_ErpBase):
    name: str | None = Field(default=None, min_length=1)
    registration_no: str | None = Field(default=None, min_length=1)
    capacity: int | None = Field(default=None, ge=1)
    status: int | None = None
    driver_staff_id: int | None = Field(default=None, ge=1)
    helper_staff_id: int | None = Field(default=None, ge=1)


class TransportRouteCreateBody(_ErpBase):
    name: str = Field(..., min_length=1)
    vehicle_id: int | None = Field(default=None, ge=1)
    description: str | None = None
    status: int = 1


class TransportRoutePatchBody(_ErpBase):
    name: str | None = Field(default=None, min_length=1)
    vehicle_id: int | None = Field(default=None, ge=1)
    description: str | None = None
    status: int | None = None


class TransportStopCreateBody(_ErpBase):
    route_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1)
    stop_order: int = 0
    pickup_time: str | None = Field(default=None, description="HH:MM or HH:MM:SS")
    drop_time: str | None = Field(default=None, description="HH:MM or HH:MM:SS")
    landmark: str | None = None


class StudentTransportAssignmentCreateBody(_ErpBase):
    student_id: int = Field(..., ge=1)
    route_id: int = Field(..., ge=1)
    stop_id: int | None = Field(default=None, ge=1)


# ---- Module 5: trips / GPS / attendance ----


class TransportTripCreateBody(_ErpBase):
    route_id: int = Field(..., ge=1)
    vehicle_id: int | None = Field(default=None, ge=1)
    driver_staff_id: int | None = Field(default=None, ge=1)


class TransportGpsBody(_ErpBase):
    model_config = ConfigDict(extra="forbid")

    lat: float
    lng: float


class TransportAttendanceBody(_ErpBase):
    model_config = ConfigDict(extra="forbid")

    student_id: int = Field(..., ge=1)
    event_type: Literal["board", "drop"]
    stop_id: int | None = Field(default=None, ge=1)

    @field_validator("event_type", mode="before")
    @classmethod
    def _normalize_event_type(cls, value: Any) -> Any:
        """Preserve service case-normalization (board/drop) before enum check."""
        if isinstance(value, str):
            return value.strip().lower()
        return value


class SalaryComponentCreateBody(_ErpBase):
    name: str = Field(..., min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    kind: Literal["earning", "deduction"] = "earning"
    calc_type: Literal["fixed", "percent"] = "fixed"
    default_value: float = Field(default=0, ge=0)
    is_active: int = Field(default=1, ge=0, le=1)
    sort_order: int = 0


class SalaryComponentPatchBody(_ErpBase):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    kind: Literal["earning", "deduction"] | None = None
    calc_type: Literal["fixed", "percent"] | None = None
    default_value: float | None = Field(default=None, ge=0)
    is_active: int | None = Field(default=None, ge=0, le=1)
    sort_order: int | None = None


def dump_erp_body(body: BaseModel) -> dict[str, Any]:
    """Serialize for services; dates stay as date objects where possible."""
    return body.model_dump(exclude_unset=True)
