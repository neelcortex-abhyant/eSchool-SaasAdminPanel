"""OpenAPI contract: no generic empty JSON request bodies (additionalProp1)."""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app

# Screenshot checklist + known former Body endpoints
_TYPED_JSON_WRITES = {
    ("POST", "/api/v1/school-admin/question-bank"),
    ("PATCH", "/api/v1/school-admin/question-bank/{question_id}"),
    ("POST", "/api/v1/school-admin/online-assessments/{assessment_id}/questions/from-bank"),
    ("POST", "/api/v1/school-admin/admission-inquiries"),
    ("PATCH", "/api/v1/school-admin/admission-inquiries/{row_id}"),
    ("POST", "/api/v1/school-admin/holidays"),
    ("PATCH", "/api/v1/school-admin/holidays/{row_id}"),
    ("POST", "/api/v1/school-admin/students/import"),
    ("POST", "/api/v1/school-admin/students/promote"),
    ("POST", "/api/v1/school-admin/students/{student_id}/transfer"),
    ("POST", "/api/v1/school-admin/students/{student_id}/reset-password"),
    ("POST", "/api/v1/school-admin/students/{student_id}/electives"),
    ("POST", "/api/v1/school-admin/semesters"),
    ("POST", "/api/v1/school-admin/streams"),
    ("POST", "/api/v1/school-admin/shifts"),
    ("POST", "/api/v1/school-admin/syllabi"),
    ("POST", "/api/v1/school-admin/online-classes"),
    ("POST", "/api/v1/school-admin/staff/import"),
    ("POST", "/api/v1/school-admin/staff-attendance"),
    ("POST", "/api/v1/school-admin/staff-tasks"),
    ("POST", "/api/v1/school-admin/expense-categories"),
    ("PUT", "/api/v1/school-admin/payroll-settings"),
    ("POST", "/api/v1/school-admin/payroll-runs"),
    ("POST", "/api/v1/school-admin/certificate-templates"),
    ("POST", "/api/v1/school-admin/certificates/issue"),
    ("PUT", "/api/v1/school-admin/id-card-settings"),
    ("POST", "/api/v1/school-admin/announcements"),
    ("POST", "/api/v1/school-admin/notifications"),
    ("POST", "/api/v1/school-admin/sliders"),
    ("POST", "/api/v1/school-admin/gallery"),
    ("POST", "/api/v1/school-admin/diary-categories"),
    ("POST", "/api/v1/school-admin/student-diaries"),
    ("PUT", "/api/v1/school-admin/staff/{user_id}/roles"),
    ("PUT", "/api/v1/school-admin/staff-qr-attendance-settings"),
}


def _schema_ref_name(op: dict) -> str | None:
    rb = op.get("requestBody") or {}
    content = (rb.get("content") or {}).get("application/json") or {}
    schema = content.get("schema") or {}
    ref = schema.get("$ref")
    return ref.rsplit("/", 1)[-1] if ref else None


def _is_generic_model(model: dict) -> bool:
    props = model.get("properties") or {}
    if model.get("additionalProperties") is True and not props:
        return True
    if not props and model.get("type", "object") == "object":
        return model.get("additionalProperties") is not False
    return False


def test_no_generic_json_request_bodies_anywhere():
    schema = app.openapi()
    comps = schema["components"]["schemas"]
    bad = []
    for path, methods in schema["paths"].items():
        for method, op in methods.items():
            if method.startswith("x-"):
                continue
            content = ((op.get("requestBody") or {}).get("content") or {})
            if "application/json" not in content:
                continue
            name = _schema_ref_name(op)
            if name == "Body" or (name and name in comps and _is_generic_model(comps[name])):
                bad.append(f"{method.upper()} {path} -> {name}")
            elif not name:
                sobj = content["application/json"].get("schema") or {}
                if _is_generic_model(sobj):
                    bad.append(f"{method.upper()} {path} -> inline generic")
    assert bad == [], "generic JSON bodies remain:\n" + "\n".join(bad)


def test_checklist_and_former_body_endpoints_have_named_properties():
    schema = app.openapi()
    comps = schema["components"]["schemas"]
    for method, path in sorted(_TYPED_JSON_WRITES):
        op = schema["paths"][path][method.lower()]
        name = _schema_ref_name(op)
        assert name is not None and name != "Body", f"{method} {path}"
        props = comps[name].get("properties") or {}
        assert props, f"{method} {path} schema {name} has empty properties"


def test_key_required_fields_documented():
    schema = app.openapi()
    comps = schema["components"]["schemas"]

    qb = comps["QuestionBankCreateBody"]
    assert set(qb.get("required") or []) >= {"question_text", "marks", "choices"}
    assert "choices" in qb["properties"]

    promote = comps["StudentsPromoteBody"]
    assert set(promote.get("required") or []) >= {"student_ids", "to_class_section_id"}

    reset = comps["StudentResetPasswordBody"]
    assert "password" in (reset.get("required") or [])

    import_body = comps["StudentsImportBody"]
    assert "rows" in import_body["properties"] or "students" in import_body["properties"]

    holiday = comps["HolidayCreateBody"]
    assert "title" in holiday["properties"]
    assert "holiday_date" in holiday["properties"]


def test_invoice_pdf_openapi_media_type():
    schema = app.openapi()
    for path in (
        "/api/v1/schools/{school_id}/invoices/{invoice_id}/pdf",
        "/api/v1/super-admin/invoices/{invoice_id}/pdf",
    ):
        op = schema["paths"][path]["get"]
        content = (op.get("responses") or {}).get("200", {}).get("content") or {}
        assert "application/pdf" in content, path


def test_routes_still_registered_for_checklist():
    paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    for _, path in _TYPED_JSON_WRITES:
        assert path in paths, path
