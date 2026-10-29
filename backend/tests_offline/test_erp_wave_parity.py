"""DB-free checks for School Admin ERP wave (Alembic 0041 + INR/installments + OpenAPI)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.routing import APIRoute

from app.main import app
from app.models.tables import (
    FeeInstallment,
    FeePayment,
    FeePaymentAllocation,
    TransportAttendanceEvent,
    TransportGpsPoint,
    TransportTrip,
    TransportVehicle,
)
from app.services.v1.school_academics import AcademicError
from app.services.v1.school_erp_fees import inr_quantize, validate_installment_sum

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_migration_0041_revises_0040():
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision("20261029_0041")
    assert rev is not None
    assert rev.down_revision == "20261028_0040"
    assert script.get_heads() == ["20261029_0042"]


def test_erp_models_have_expected_columns():
    assert "cancelled_at" in FeePayment.__table__.c
    assert "cancel_reason" in FeePayment.__table__.c
    assert "driver_staff_id" in TransportVehicle.__table__.c
    assert "helper_staff_id" in TransportVehicle.__table__.c
    assert "school_id" in FeeInstallment.__table__.c
    assert "installment_id" in FeePaymentAllocation.__table__.c
    assert FeePaymentAllocation.__table__.c.installment_id.nullable is True
    assert "status" in TransportTrip.__table__.c
    assert "expires_at" in TransportGpsPoint.__table__.c
    assert "event_type" in TransportAttendanceEvent.__table__.c


def test_inr_quantize_half_up():
    assert inr_quantize("10.005") == Decimal("10.01")
    assert inr_quantize("10.004") == Decimal("10.00")
    assert inr_quantize(1.1 + 2.2) == Decimal("3.30")


def test_installment_sum_must_equal_structure_total():
    validate_installment_sum(
        Decimal("100.00"),
        [
            {"name": "A", "due_date": "2026-01-01", "amount": "40.00"},
            {"name": "B", "due_date": "2026-02-01", "amount": "60.00"},
        ],
    )
    with pytest.raises(AcademicError) as exc:
        validate_installment_sum(
            100,
            [
                {"name": "A", "due_date": "2026-01-01", "amount": "40"},
                {"name": "B", "due_date": "2026-02-01", "amount": "50"},
            ],
        )
    assert exc.value.status_code == 422


def test_openapi_registers_key_erp_paths():
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    for path in (
        "/api/v1/school-admin/report-cards/{report_id}/pdf",
        "/api/v1/school-admin/fee-structures/{structure_id}/installments",
        "/api/v1/school-admin/fee-payments/{payment_id}/receipt",
        "/api/v1/school-admin/fee-payments/{payment_id}/receipt/pdf",
        "/api/v1/school-admin/fee-payments/{payment_id}/cancel",
        "/api/v1/school-admin/fees/collection-report",
        "/api/v1/school-admin/salary-components",
        "/api/v1/school-admin/transport-trips",
        "/api/v1/school-admin/transport-trips/{trip_id}/start",
        "/api/v1/school-admin/transport-trips/{trip_id}/complete",
        "/api/v1/school-admin/transport-trips/{trip_id}/gps",
        "/api/v1/school-admin/transport-trips/{trip_id}/attendance",
        "/api/v1/school-admin/transport/reports/trips",
        "/api/v1/public/schools/by-host",
        "/api/v1/public/schools/by-code",
        "/api/staff/transport/my-trips",
        "/api/staff/transport/trips/{trip_id}/gps",
        "/api/staff/transport/trips/{trip_id}/attendance",
        "/api/student/report-cards",
        "/api/student/fees/balance",
        "/api/parent/children/{student_id}/transport/live",
    ):
        assert path in route_paths, path
