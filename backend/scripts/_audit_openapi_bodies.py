"""Audit OpenAPI for generic/empty JSON request bodies."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

schema = app.openapi()
paths = schema.get("paths") or {}
comps = schema.get("components", {}).get("schemas", {})


def body_info(op: dict):
    rb = op.get("requestBody") or {}
    content = rb.get("content") or {}
    json_c = content.get("application/json") or {}
    mp = content.get("multipart/form-data") or {}
    schema_obj = json_c.get("schema") or mp.get("schema") or {}
    ref = schema_obj.get("$ref")
    name = ref.rsplit("/", 1)[-1] if ref else None
    if "application/json" in content:
        media = "json"
    elif "multipart/form-data" in content:
        media = "multipart"
    elif content:
        media = list(content.keys())[0]
    else:
        media = None
    return name, schema_obj, media, content


def is_generic_model(model: dict) -> str | None:
    props = model.get("properties") or {}
    if model.get("additionalProperties") is True and not props:
        return "additionalProperties-only"
    if not props and model.get("type", "object") == "object":
        # empty object schema used as Body
        if "properties" not in model or props == {}:
            if model.get("additionalProperties") is not False:
                return "empty-object"
    return None


generic: list[tuple] = []
ops_total = 0
with_body = 0
pdf_issues: list[tuple] = []
json_resp_missing_ref: list[tuple] = []
checklist = [
    "/api/v1/school-admin/question-bank",
    "/api/v1/school-admin/admission-inquiries",
    "/api/v1/school-admin/holidays",
    "/api/v1/school-admin/students/import",
    "/api/v1/school-admin/students/promote",
    "/api/v1/school-admin/students/{student_id}/transfer",
    "/api/v1/school-admin/students/{student_id}/reset-password",
    "/api/v1/school-admin/students/{student_id}/electives",
    "/api/v1/school-admin/semesters",
    "/api/v1/school-admin/streams",
    "/api/v1/school-admin/shifts",
    "/api/v1/school-admin/syllabi",
    "/api/v1/school-admin/online-classes",
    "/api/v1/school-admin/staff/import",
    "/api/v1/school-admin/staff-attendance",
    "/api/v1/school-admin/staff-tasks",
    "/api/v1/school-admin/expense-categories",
]

for path, methods in sorted(paths.items()):
    for method, op in methods.items():
        if method.startswith("x-"):
            continue
        ops_total += 1
        name, sobj, media, content = body_info(op)
        if content:
            with_body += 1
            reason = None
            if name == "Body":
                reason = "named Body"
            elif name and name in comps:
                reason = is_generic_model(comps[name])
                if reason:
                    reason = f"{name}:{reason}"
            elif not name and sobj:
                reason = is_generic_model(sobj)
                if reason:
                    reason = f"inline:{reason}"
            if reason and media == "json":
                generic.append((method.upper(), path, reason, name))

        if "pdf" in path.lower() and method.lower() == "get":
            ok = (op.get("responses") or {}).get("200") or {}
            rc = ok.get("content") or {}
            if "application/pdf" not in rc:
                pdf_issues.append((method.upper(), path, list(rc.keys())))

        if method.upper() in {"GET", "POST", "PUT", "PATCH"}:
            for code in ("200", "201"):
                ok = (op.get("responses") or {}).get(code)
                if not ok:
                    continue
                rc = ok.get("content") or {}
                if "application/json" in rc:
                    js = rc["application/json"].get("schema") or {}
                    if not js.get("$ref") and not js.get("type") and not js.get("properties") and not js.get("items"):
                        json_resp_missing_ref.append((method.upper(), path, code))

print(f"ops={ops_total} with_body={with_body} generic_json={len(generic)} pdf_issues={len(pdf_issues)}")
print("=== GENERIC JSON BODIES ===")
for row in generic:
    print(f"{row[0]:6} {row[1]}  [{row[2]}]")

print("\n=== CHECKLIST STATUS ===")
generic_set = {(m, p) for m, p, *_ in generic}
for path in checklist:
    post = paths.get(path, {}).get("post")
    if not post:
        print(f"MISSING POST {path}")
        continue
    name, sobj, media, content = body_info(post)
    bad = ("POST", path) in generic_set
    print(f"{'BAD ' if bad else 'OK  '} POST {path} media={media} schema={name}")

print("\n=== PDF ISSUES ===")
for row in pdf_issues:
    print(row)

out = Path(__file__).resolve().parents[1] / "docs" / "_openapi_generic_bodies.json"
out.write_text(json.dumps({"generic": generic, "ops": ops_total, "with_body": with_body}, indent=2), encoding="utf-8")
print(f"\nWrote {out}")
