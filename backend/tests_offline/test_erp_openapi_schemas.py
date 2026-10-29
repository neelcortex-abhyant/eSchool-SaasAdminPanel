"""OpenAPI accuracy for School Admin ERP modules 1–5 (no DB)."""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from pydantic import ValidationError

from app.main import app
from app.schemas.v1.school_admin_erp import TransportAttendanceBody

# Write endpoints that previously used empty Body → additionalProp1
_ERP_TYPED_WRITE_PATHS = {
    ("POST", "/api/v1/school-admin/grading-scales"),
    ("PATCH", "/api/v1/school-admin/grading-scales/{scale_id}"),
    ("POST", "/api/v1/school-admin/report-cards"),
    ("POST", "/api/v1/school-admin/fee-types"),
    ("PATCH", "/api/v1/school-admin/fee-types/{row_id}"),
    ("POST", "/api/v1/school-admin/fee-structures"),
    ("PATCH", "/api/v1/school-admin/fee-structures/{row_id}"),
    ("PUT", "/api/v1/school-admin/fee-structures/{structure_id}/installments"),
    ("POST", "/api/v1/school-admin/fee-assignments"),
    ("POST", "/api/v1/school-admin/fee-concessions"),
    ("POST", "/api/v1/school-admin/fees/collect"),
    ("POST", "/api/v1/school-admin/fee-payments/{payment_id}/cancel"),
    ("POST", "/api/v1/school-admin/vehicles"),
    ("PATCH", "/api/v1/school-admin/vehicles/{row_id}"),
    ("POST", "/api/v1/school-admin/transport-routes"),
    ("PATCH", "/api/v1/school-admin/transport-routes/{row_id}"),
    ("POST", "/api/v1/school-admin/transport-stops"),
    ("POST", "/api/v1/school-admin/student-transport-assignments"),
    ("POST", "/api/v1/school-admin/transport-trips"),
    ("POST", "/api/v1/school-admin/transport-trips/{trip_id}/gps"),
    ("POST", "/api/v1/school-admin/transport-trips/{trip_id}/attendance"),
    ("POST", "/api/staff/transport/trips/{trip_id}/gps"),
    ("POST", "/api/staff/transport/trips/{trip_id}/attendance"),
}

_PDF_PATHS = {
    "/api/v1/school-admin/report-cards/{report_id}/pdf",
    "/api/v1/school-admin/fee-payments/{payment_id}/receipt/pdf",
    "/api/student/report-cards/{report_id}/pdf",
    "/api/student/fees/payments/{payment_id}/receipt/pdf",
    "/api/parent/children/{student_id}/report-cards/{report_id}/pdf",
    "/api/parent/children/{student_id}/fees/payments/{payment_id}/receipt/pdf",
}

_JSON_RESPONSE_SAMPLE_PATHS = {
    ("GET", "/api/v1/school-admin/grading-scales"),
    ("GET", "/api/v1/school-admin/fees/outstanding"),
    ("GET", "/api/v1/school-admin/fee-payments/{payment_id}/receipt"),
    ("GET", "/api/v1/school-admin/transport-trips"),
    ("GET", "/api/student/fees/balance"),
    ("GET", "/api/parent/children/{student_id}/transport/live"),
    ("POST", "/api/v1/school-admin/fees/collect"),
}


def _schema_ref_name(op: dict) -> str | None:
    rb = op.get("requestBody") or {}
    content = (rb.get("content") or {}).get("application/json") or {}
    schema = content.get("schema") or {}
    ref = schema.get("$ref")
    if ref:
        return ref.rsplit("/", 1)[-1]
    return None


def _response_schema(op: dict, code: str = "200") -> dict:
    responses = op.get("responses") or {}
    r = responses.get(code) or responses.get("200") or {}
    return ((r.get("content") or {}).get("application/json") or {}).get("schema") or {}


def test_erp_write_endpoints_have_named_non_empty_body_schemas():
    schema = app.openapi()
    comps = schema["components"]["schemas"]
    for method, path in sorted(_ERP_TYPED_WRITE_PATHS):
        op = schema["paths"][path][method.lower()]
        name = _schema_ref_name(op)
        assert name is not None, f"{method} {path} missing schema $ref"
        assert name != "Body", f"{method} {path} still uses generic Body"
        model = comps[name]
        props = model.get("properties") or {}
        assert props, f"{method} {path} schema {name} has empty properties"
        assert not (
            model.get("additionalProperties") is True and not props
        ), f"{method} {path} still additionalProperties-only"


def test_erp_collect_and_installments_document_required_fields():
    schema = app.openapi()
    comps = schema["components"]["schemas"]

    collect_ref = _schema_ref_name(schema["paths"]["/api/v1/school-admin/fees/collect"]["post"])
    collect = comps[collect_ref]
    assert "assignment_id" in collect["properties"]
    assert "amount" in collect["properties"]
    assert set(collect.get("required") or []) >= {"assignment_id", "amount"}

    put_ref = _schema_ref_name(
        schema["paths"]["/api/v1/school-admin/fee-structures/{structure_id}/installments"]["put"]
    )
    put_model = comps[put_ref]
    assert "installments" in put_model["properties"] or "items" in put_model["properties"]

    cancel_ref = _schema_ref_name(
        schema["paths"]["/api/v1/school-admin/fee-payments/{payment_id}/cancel"]["post"]
    )
    cancel = comps[cancel_ref]
    assert cancel["properties"]["reason"]["minLength"] == 1
    assert "reason" in (cancel.get("required") or [])


def test_attendance_event_type_enum_in_openapi():
    schema = app.openapi()
    comps = schema["components"]["schemas"]
    for path in (
        "/api/v1/school-admin/transport-trips/{trip_id}/attendance",
        "/api/staff/transport/trips/{trip_id}/attendance",
    ):
        ref = _schema_ref_name(schema["paths"][path]["post"])
        et = comps[ref]["properties"]["event_type"]
        assert "board" in (et.get("enum") or [])
        assert "drop" in (et.get("enum") or [])


def test_attendance_event_type_accepts_case_normalized_values():
    ok = TransportAttendanceBody(student_id=1, event_type="Board")
    assert ok.event_type == "board"
    ok2 = TransportAttendanceBody(student_id=1, event_type=" DROP ")
    assert ok2.event_type == "drop"


def test_attendance_event_type_rejects_invalid_values():
    with pytest.raises(ValidationError):
        TransportAttendanceBody(student_id=1, event_type="pickup")
    with pytest.raises(ValidationError):
        TransportAttendanceBody(student_id=1, event_type="")


def test_pdf_endpoints_advertise_application_pdf():
    schema = app.openapi()
    for path in sorted(_PDF_PATHS):
        op = schema["paths"][path]["get"]
        content = (op.get("responses") or {}).get("200", {}).get("content") or {}
        assert "application/pdf" in content, f"{path} missing application/pdf in OpenAPI"


def test_erp_json_responses_document_properties():
    schema = app.openapi()
    comps = schema["components"]["schemas"]
    for method, path in sorted(_JSON_RESPONSE_SAMPLE_PATHS):
        op = schema["paths"][path][method.lower()]
        code = "201" if method == "POST" and "collect" in path else "200"
        sch = _response_schema(op, code)
        ref = sch.get("$ref")
        assert ref, f"{method} {path} missing response $ref (got {sch})"
        name = ref.rsplit("/", 1)[-1]
        props = (comps.get(name) or {}).get("properties") or {}
        assert props, f"{method} {path} response schema {name} has no properties"


def test_no_erp_write_uses_generic_body_title():
    schema = app.openapi()
    for method, path in _ERP_TYPED_WRITE_PATHS:
        name = _schema_ref_name(schema["paths"][path][method.lower()])
        assert name != "Body"


def test_erp_routes_still_registered():
    paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/school-admin/fees/collect" in paths
    assert "/api/v1/school-admin/fee-structures/{structure_id}/installments" in paths
    assert "/api/parent/children/{student_id}/transport/live" in paths
