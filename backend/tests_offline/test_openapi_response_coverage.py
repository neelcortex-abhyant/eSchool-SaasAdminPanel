"""OpenAPI named response-schema coverage for Phase 2."""

from __future__ import annotations

from app.main import app

# Representative school-admin writes that must document named JSON success models
_REQUIRED_NAMED_RESPONSES = {
    ("POST", "/api/v1/school-admin/question-bank", "201"),
    ("POST", "/api/v1/school-admin/admission-inquiries", "201"),
    ("POST", "/api/v1/school-admin/holidays", "201"),
    ("POST", "/api/v1/school-admin/students/promote", "200"),
    ("POST", "/api/v1/school-admin/students/import", "201"),
    ("POST", "/api/v1/school-admin/semesters", "201"),
    ("POST", "/api/v1/school-admin/staff-tasks", "201"),
    ("POST", "/api/v1/school-admin/expense-categories", "201"),
    ("POST", "/api/v1/school-admin/salary-components", "201"),
    ("POST", "/api/v1/school-admin/timetable-entries", "201"),
    ("POST", "/api/v1/school-admin/students", "201"),
    ("POST", "/api/v1/school-admin/teachers", "201"),
    ("POST", "/api/v1/school-admin/homework", "201"),
    ("PUT", "/api/v1/school-admin/leave-settings", "200"),
    ("PUT", "/api/v1/school-admin/whatsapp-settings", "200"),
    ("POST", "/api/v1/school-admin/study-materials", "201"),
    ("POST", "/api/v1/school-admin/online-assessments", "201"),
    ("POST", "/api/v1/school-admin/academics/{resource}", "201"),
    # Former remaining-27 school-admin write gaps
    ("POST", "/api/v1/school-admin/offline-exams", "201"),
    ("POST", "/api/v1/school-admin/offline-exams/{exam_id}/process-results", "200"),
    ("POST", "/api/v1/school-admin/online-assessments/{assessment_id}/questions", "201"),
    ("POST", "/api/v1/school-admin/study-materials/upload", "201"),
    ("POST", "/api/v1/school-admin/students/{student_id}/documents", "201"),
    ("POST", "/api/v1/school-admin/support-tickets", "201"),
    ("PUT", "/api/v1/school-admin/online-exam-terms", "200"),
    ("PUT", "/api/v1/school-admin/subjects/{subject_id}/classes", "200"),
}


def _success_ref(op: dict, code: str) -> str | None:
    ok = (op.get("responses") or {}).get(code) or {}
    schema = ((ok.get("content") or {}).get("application/json") or {}).get("schema") or {}
    ref = schema.get("$ref")
    return ref.rsplit("/", 1)[-1] if ref else None


def test_representative_writes_have_named_response_models():
    schema = app.openapi()
    comps = schema["components"]["schemas"]
    for method, path, code in sorted(_REQUIRED_NAMED_RESPONSES):
        op = schema["paths"][path][method.lower()]
        name = _success_ref(op, code)
        assert name, f"{method} {path} missing named {code} response"
        props = comps[name].get("properties") or {}
        assert props, f"{method} {path} response {name} has empty properties"


def test_question_bank_and_promote_response_fields():
    schema = app.openapi()
    comps = schema["components"]["schemas"]
    qb = comps["QuestionBankOut"]["properties"]
    assert "question_text" in qb and "choices" in qb and "marks" in qb
    promote = comps["StudentsPromoteOut"]["properties"]
    assert "promoted" in promote and "count" in promote
    tt = comps["TimetableEntryOut"]["properties"]
    assert "room" in tt and "day" in tt and "start_time" in tt


def test_integration_settings_response_excludes_secrets():
    schema = app.openapi()
    props = schema["components"]["schemas"]["IntegrationSettingsOut"]["properties"]
    assert "configured" in props
    assert "public_config" in props
    assert "secret_ciphertext" not in props
    assert "secret" not in props


def test_school_admin_write_named_response_count_improved():
    """Guardrail: school-admin JSON write ops with named responses stay high."""
    schema = app.openapi()
    named = 0
    missing = 0
    for path, methods in schema["paths"].items():
        if "/school-admin/" not in path:
            continue
        for method, op in methods.items():
            if method not in {"post", "put", "patch"}:
                continue
            for code in ("200", "201"):
                ok = (op.get("responses") or {}).get(code)
                if not ok:
                    continue
                content = ok.get("content") or {}
                if "application/json" not in content:
                    continue
                js = content["application/json"].get("schema") or {}
                if js.get("$ref"):
                    named += 1
                else:
                    missing += 1
    # Master-task: all school-admin JSON write ops must have named success schemas.
    assert named >= 100, f"expected >=100 named school-admin write responses, got {named}"
    assert missing == 0, f"expected 0 missing school-admin write responses, got {missing}"


def test_generic_request_bodies_still_zero():
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
            ref = (content["application/json"].get("schema") or {}).get("$ref")
            name = ref.rsplit("/", 1)[-1] if ref else None
            if name == "Body":
                bad.append(f"{method.upper()} {path}")
            elif name and name in comps:
                model = comps[name]
                props = model.get("properties") or {}
                if model.get("additionalProperties") is True and not props:
                    bad.append(f"{method.upper()} {path}")
    assert bad == []
