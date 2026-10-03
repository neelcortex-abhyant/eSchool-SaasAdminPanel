#!/usr/bin/env python3
"""Smoke student-web API contract against FastAPI (no Next.js required).

Hits the student-web auth/bootstrap paths used by the Next.js portal.
Uses sanitized dataset credentials: DEMOA / GR001 / secret.

Usage (from AdminPanel root; prefer backend venv for httpx):
  backend/.venv/bin/python contract-tests/scripts/smoke_student_web_api.py
  TEST_BASE_URL=http://127.0.0.1:8001 backend/.venv/bin/python contract-tests/scripts/smoke_student_web_api.py

Exit codes:
  0  all checks passed
  1  HTTP/contract failure
  2  connection refused / FastAPI not reachable, or missing httpx
"""
from __future__ import annotations

import os
import sys

try:
    import httpx
except ImportError:
    print(
        "FAIL: httpx is required. Use the backend venv, e.g.\n"
        "  /Users/apple/eSchool-SaasAdminPanel/backend/.venv/bin/python "
        "contract-tests/scripts/smoke_student_web_api.py",
        file=sys.stderr,
    )
    raise SystemExit(2)

BASE = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
SCHOOL = os.environ.get("TEST_SCHOOL_CODE", "DEMOA")
GR = os.environ.get("TEST_GR_NUMBER", "GR001")
PASSWORD = os.environ.get("TEST_PASSWORD", "secret")
TIMEOUT = float(os.environ.get("TEST_TIMEOUT", "10"))


def fail(msg: str, code: int = 1) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(code)


def ok(msg: str) -> None:
    print(f"OK: {msg}")


def assert_success_envelope(body: dict, step: str) -> None:
    if not isinstance(body, dict):
        fail(f"{step}: expected JSON object, got {type(body).__name__}")
    if body.get("error") is True:
        fail(f"{step}: error envelope {body!r}")
    if body.get("error") not in (False, 0, None) and "data" not in body and "token" not in body:
        # Laravel-shaped success usually has error=false; tolerate token-only login shape.
        fail(f"{step}: unexpected body {body!r}")


def main() -> None:
    print(f"Smoke student-web API against {BASE}")
    try:
        with httpx.Client(base_url=BASE, timeout=TIMEOUT) as client:
            # Multipart form — matches student-web / Laravel FormData login
            login = client.post(
                "/api/student/login",
                files={
                    "gr_number": (None, GR),
                    "password": (None, PASSWORD),
                    "school_code": (None, SCHOOL),
                    "fcm_id": (None, "smoke-student-web"),
                },
            )
            if login.status_code >= 500:
                fail(f"login HTTP {login.status_code}: {login.text[:300]}")
            login_body = login.json()
            assert_success_envelope(login_body, "login")
            token = login_body.get("token")
            if not token:
                fail(f"login: missing token in {login_body!r}")
            ok(f"POST /api/student/login ({SCHOOL}/{GR})")

            headers = {
                "Authorization": f"Bearer {token}",
                "school-code": SCHOOL,
            }

            profile = client.get("/api/student/get-profile-data", headers=headers)
            profile_body = profile.json()
            assert_success_envelope(profile_body, "get-profile-data")
            data = profile_body.get("data") or {}
            if data.get("admission_no") != GR:
                fail(f"get-profile-data: expected admission_no={GR}, got {data.get('admission_no')!r}")
            ok("GET /api/student/get-profile-data")

            settings = client.get("/api/school-settings", headers=headers)
            settings_body = settings.json()
            assert_success_envelope(settings_body, "school-settings")
            if "data" not in settings_body:
                fail(f"school-settings: missing data {settings_body!r}")
            ok("GET /api/school-settings")

            years = client.get("/api/session-years", headers=headers)
            years_body = years.json()
            assert_success_envelope(years_body, "session-years")
            if not years_body.get("data"):
                fail(f"session-years: empty data {years_body!r}")
            ok("GET /api/session-years")

            logout = client.post(
                "/api/logout",
                files={"fcm_id": (None, "smoke-student-web")},
                headers=headers,
            )
            logout_body = logout.json()
            assert_success_envelope(logout_body, "logout")
            ok("POST /api/logout")

    except httpx.ConnectError as exc:
        fail(
            f"connection refused to {BASE} — start FastAPI on :8001 "
            f"(or set TEST_BASE_URL). Detail: {exc}",
            code=2,
        )
    except httpx.TimeoutException as exc:
        fail(f"timeout talking to {BASE}: {exc}", code=2)
    except httpx.HTTPError as exc:
        fail(f"HTTP transport error: {exc}", code=2)

    print("PASS: student-web API smoke completed")


if __name__ == "__main__":
    main()
