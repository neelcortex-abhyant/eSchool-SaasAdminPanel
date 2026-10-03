#!/usr/bin/env python3
"""Regenerate backend/app/api/stubs.py from reconciled_manifest.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAN = ROOT / "contract-tests/manifest/reconciled_manifest.json"
OUT = ROOT / "backend/app/api/stubs.py"

IMPLEMENTED = {
    ("POST", "/api/student/login"),
    ("POST", "/api/parent/login"),
    ("POST", "/api/teacher/login"),
    ("POST", "/api/staff/login"),
    ("POST", "/api/logout"),
    ("GET", "/api/staff/features-permission"),
    ("GET", "/api/settings"),
    ("GET", "/api/school-settings"),
    ("GET", "/api/student/school-settings"),
    ("GET", "/api/get-languages"),
    ("POST", "/api/set-languages"),
    ("GET", "/api/holidays"),
    ("GET", "/api/notifications"),
    ("GET", "/api/gallery"),
    ("GET", "/api/session-years"),
    ("GET", "/api/student/get-profile-data"),
    ("GET", "/api/student/subjects"),
    ("GET", "/api/student/timetable"),
    ("GET", "/api/student/attendance"),
    ("GET", "/api/student/assignments"),
    ("GET", "/api/student/get-exam-list"),
    ("GET", "/api/student/announcements"),
    ("GET", "/api/student/guradian-details"),
    ("GET", "/api/parent/get-data"),
    ("GET", "/api/parent/subjects"),
    ("GET", "/api/parent/attendance"),
    ("GET", "/api/parent/get-exam-list"),
    ("GET", "/api/parent/announcements"),
    ("GET", "/api/parent/school-settings"),
    ("GET", "/api/school-details"),
    ("POST", "/api/change-password"),
    ("POST", "/api/forgot-password"),
    ("GET", "/api/profile"),
    ("GET", "/api/staff/counter"),
    ("GET", "/api/classes"),
    ("GET", "/api/staff/teachers"),
    ("GET", "/api/leaves"),
    ("POST", "/api/leaves"),
    ("GET", "/api/medium"),
    ("GET", "/api/country-codes"),
    ("POST", "/api/parent/store-fees"),
    ("POST", "/api/parent/fail-payment-transaction"),
    ("POST", "/api/message/read"),
    ("POST", "/api/delete/message"),
    ("POST", "/api/webhook/stripe"),
    ("POST", "/api/webhook/razorpay"),
    ("POST", "/api/webhook/paystack"),
    ("POST", "/api/webhook/flutterwave"),
    ("GET", "/api/diaries"),
    ("GET", "/api/student-details"),
    ("GET", "/api/pickup-points"),
    ("GET", "/api/transportation-shifts"),
    ("GET", "/api/transportation-fees"),
}

def main():
    data = json.loads(MAN.read_text())
    seen = set()
    uniq = []
    for r in data["routes"]:
        key = (r["method"], r["path"])
        if key in IMPLEMENTED or key in seen:
            continue
        if r["status"] in ("dead_or_admin_only", "dead_client_constant"):
            continue
        if r["client_count"] == 0 and r["status"] != "active_external":
            continue
        if r["method"] not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            continue
        seen.add(key)
        uniq.append(r)
    lines = [
        '"""Auto-generated contract stubs for Phases 5–7.',
        "",
        "Each stub returns a Laravel-shaped error envelope marking the route as not yet ported.",
        "Do not canary these paths until implementation + golden fixtures pass.",
        "Regenerate: python3 contract-tests/scripts/generate_stubs.py (embedded in Phase execution).",
        '"""',
        "from __future__ import annotations",
        "",
        "from fastapi import APIRouter, Request",
        "",
        "from app.core.responses import fail",
        "",
        "router = APIRouter()",
        "",
        "",
        "def _stub(request: Request):",
        "    return fail(",
        '        f"Route not yet ported: {request.method} {request.url.path}",',
        "        code=501,",
        '        details="contract-stub",',
        "    )",
        "",
    ]
    for r in uniq:
        full = r["path"]
        if not full.startswith("/api/"):
            continue
        path = full[4:]
        method = r["method"].lower()
        name = "stub_" + method + "_" + full.strip("/").replace("/", "_").replace("-", "_")
        name = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
        lines += [f"@router.{method}('{path}')", f"async def {name}(request: Request):", "    return _stub(request)", ""]
    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT} ({len(uniq)} stubs)")

if __name__ == "__main__":
    main()
