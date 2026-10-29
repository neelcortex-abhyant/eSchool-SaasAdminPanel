"""DB-free regression checks for FE-reported API gaps (Alembic 0042)."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.routing import APIRoute

from app.main import app
from app.models.tables import ClassTimetableEntry, SalaryComponent
from app.schemas.v1.school_admin_erp import FeeStructureCreateBody, SalaryComponentCreateBody
from app.schemas.v1.school_admin_erp_responses import FeeStructureOut, SalaryComponentOut
from app.services.v1.public_school_lookup import _public_payload

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_migration_0042_revises_0041():
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision("20261029_0042")
    assert rev is not None
    assert rev.down_revision == "20261029_0041"
    assert script.get_heads() == ["20261029_0042"]


def test_timetable_room_column_and_salary_component_model():
    assert "room" in ClassTimetableEntry.__table__.c
    assert ClassTimetableEntry.__table__.c.room.nullable is True
    assert SalaryComponent.__tablename__ == "salary_components"
    for col in (
        "school_id",
        "name",
        "code",
        "kind",
        "calc_type",
        "default_value",
        "is_active",
        "sort_order",
        "deleted_at",
    ):
        assert col in SalaryComponent.__table__.c, col


def test_public_school_lookup_routes_registered():
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/public/schools/by-host" in route_paths
    assert "/api/v1/public/schools/by-code" in route_paths


def test_salary_component_routes_registered():
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/school-admin/salary-components" in route_paths
    assert "/api/v1/school-admin/salary-components/{row_id}" in route_paths


def test_openapi_public_lookup_and_salary_and_room():
    schema = app.openapi()
    paths = schema["paths"]
    comps = schema["components"]["schemas"]

    by_host = paths["/api/v1/public/schools/by-host"]["get"]
    assert any(p.get("name") == "host" for p in (by_host.get("parameters") or []))

    by_code = paths["/api/v1/public/schools/by-code"]["get"]
    assert any(p.get("name") == "code" for p in (by_code.get("parameters") or []))

    create_tt = paths["/api/v1/school-admin/timetable-entries"]["post"]
    tt_ref = (
        (create_tt.get("requestBody") or {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref", "")
    )
    tt_name = tt_ref.rsplit("/", 1)[-1]
    assert "room" in (comps[tt_name].get("properties") or {})

    patch_tt = paths["/api/v1/school-admin/timetable-entries/{entry_id}"]["patch"]
    patch_ref = (
        (patch_tt.get("requestBody") or {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref", "")
    )
    patch_name = patch_ref.rsplit("/", 1)[-1]
    assert "room" in (comps[patch_name].get("properties") or {})

    salary_post = paths["/api/v1/school-admin/salary-components"]["post"]
    sal_ref = (
        (salary_post.get("requestBody") or {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref", "")
    )
    sal_name = sal_ref.rsplit("/", 1)[-1]
    props = comps[sal_name].get("properties") or {}
    for field in ("name", "code", "kind", "calc_type", "default_value", "is_active", "sort_order"):
        assert field in props, field

    assert "installments" in comps["FeeStructureOut"]["properties"]


def test_fee_structure_create_body_accepts_installments():
    body = FeeStructureCreateBody(
        name="Annual",
        session_year_id=1,
        amounts=[{"fee_type_id": 1, "amount": 100}],
        installments=[
            {"name": "Term 1", "due_date": "2026-04-01", "amount": 50},
            {"name": "Term 2", "due_date": "2026-10-01", "amount": 50},
        ],
    )
    assert body.installments is not None
    assert len(body.installments) == 2


def test_salary_component_create_schema():
    row = SalaryComponentCreateBody(
        name="Basic Pay",
        code="BASIC",
        kind="earning",
        calc_type="fixed",
        default_value=25000,
    )
    assert row.kind == "earning"
    assert row.model_dump()["name"] == "Basic Pay"


def test_public_payload_excludes_private_fields():
    class _S:
        id = 9
        name = "Green Valley"
        domain = "greenvalley.example.com"
        domain_type = "default"
        domain_verified = 1
        tagline = "Learn"
        logo = None
        address = "Street 1"
        support_phone = "999"
        support_email = "a@b.c"
        status = 1
        provisioned_at = object()
        code = "GV01"

    payload = _public_payload(_S())  # type: ignore[arg-type]
    assert payload["school_id"] == 9
    assert payload["name"] == "Green Valley"
    assert "admin_email" not in payload
    assert "razorpay" not in str(payload).lower()
    assert "password" not in str(payload).lower()
    # by-host must not auto-include code; by-code adds it explicitly
    assert "code" not in payload


def test_fee_structure_out_documents_installments():
    model = FeeStructureOut.model_validate(
        {
            "id": 1,
            "school_id": 1,
            "name": "Fees",
            "session_year_id": 1,
            "status": 1,
            "amounts": [],
            "total": 0,
            "installments": [
                {
                    "id": 1,
                    "structure_id": 1,
                    "name": "T1",
                    "due_date": "2026-01-01",
                    "amount": 10.0,
                    "sort_order": 0,
                    "allocated": 0.0,
                    "outstanding": 10.0,
                }
            ],
        }
    )
    assert len(model.installments) == 1


def test_salary_component_out_fields():
    model = SalaryComponentOut.model_validate(
        {
            "id": 1,
            "school_id": 1,
            "name": "HRA",
            "code": "HRA",
            "kind": "earning",
            "calc_type": "percent",
            "default_value": 40.0,
            "is_active": 1,
            "sort_order": 2,
        }
    )
    assert model.calc_type == "percent"


def test_create_leave_requires_user_or_student_id():
    from datetime import date
    from unittest.mock import MagicMock

    import pytest

    from app.services.v1.school_academics import AcademicError, create_leave

    with pytest.raises(AcademicError) as exc:
        create_leave(
            MagicMock(),
            1,
            {
                "reason": "Sick",
                "from_date": date(2026, 1, 1),
                "to_date": date(2026, 1, 2),
                "session_year_id": 1,
            },
        )
    assert exc.value.status_code == 422
    assert "user_id or student_id" in str(exc.value.detail)
