#!/usr/bin/env python3
"""Capture sanitized golden fixtures for auth/bootstrap from local SQLite mirrors."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OUT = ROOT / "contract-tests" / "fixtures" / "golden"
sys.path.insert(0, str(BACKEND))

MIRROR = ROOT / "datasets" / "sqlite_mirror"
os.environ["DB_CONNECTION"] = "sqlite"
os.environ["SQLITE_DIR"] = str(MIRROR)
os.environ["DB_DATABASE"] = "eschool_central"
os.environ["ALLOW_DDL"] = "false"
os.environ["APP_ENV"] = "local"

from app.core.config import get_settings
from app.core.database import reset_engines

get_settings.cache_clear()
reset_engines()

from fastapi.testclient import TestClient
from app.main import app


TOKEN_RE = re.compile(r"^\d+\|[A-Za-z0-9_\-]+$")


def sanitize(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "token" and isinstance(v, str) and TOKEN_RE.match(v):
                out[k] = "REDACTED_TOKEN"
            elif k in {"fcm_id", "web_fcm"} and isinstance(v, str) and v:
                out[k] = "REDACTED_FCM"
            else:
                out[k] = sanitize(v)
        return out
    if isinstance(obj, list):
        return [sanitize(x) for x in obj]
    return obj


def write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize(payload), indent=2, sort_keys=True) + "\n")
    print("wrote", path)


def main() -> None:
    if not (MIRROR / "eschool_central.db").exists():
        raise SystemExit("Run datasets/seed_sqlite_mirror.py first")

    with TestClient(app) as client:
        student = client.post(
            "/api/student/login",
            data={"gr_number": "GR001", "password": "secret", "school_code": "DEMOA", "fcm_id": "fcm-student"},
        ).json()
        write(OUT / "student" / "login_success.json", student)

        parent = client.post(
            "/api/parent/login",
            data={"email": "guardian@school.test", "password": "secret", "school_code": "DEMOA", "fcm_id": "fcm-parent"},
        ).json()
        write(OUT / "parent" / "login_success.json", parent)

        teacher = client.post(
            "/api/teacher/login",
            data={"email": "teacher@school.test", "password": "secret", "school_code": "DEMOA"},
        ).json()
        write(OUT / "teacher" / "login_success.json", teacher)

        school_admin = client.post(
            "/api/teacher/login",
            data={"email": "schooladmin@demoa.test", "password": "secret", "school_code": "DEMOA"},
        ).json()
        write(OUT / "school_admin" / "login_success.json", school_admin)

        driver = client.post(
            "/api/teacher/login",
            data={"email": "driver@demoa.test", "password": "secret", "school_code": "DEMOA"},
        ).json()
        write(OUT / "driver" / "login_success.json", driver)

        # Logout variants using teacher token
        token = teacher["token"]
        for name, data in [
            ("logout_fcm_id", {"fcm_id": "fcm-x"}),
            ("logout_device_id", {"device_id": "device-1"}),
            ("logout_web_fcm", {"web_fcm": "web-fcm-1"}),
            ("logout_no_device", {}),
        ]:
            # re-login for each
            again = client.post(
                "/api/teacher/login",
                data={"email": "teacher@school.test", "password": "secret", "school_code": "DEMOA"},
            ).json()
            tok = again["token"]
            resp = client.post(
                "/api/logout",
                data=data,
                headers={"school-code": "DEMOA", "Authorization": f"Bearer {tok}"},
            ).json()
            write(OUT / "auth" / f"{name}.json", resp)

        features = client.post(
            "/api/teacher/login",
            data={"email": "teacher@school.test", "password": "secret", "school_code": "DEMOA"},
        ).json()
        feat = client.get(
            "/api/staff/features-permission",
            headers={"school-code": "DEMOA", "Authorization": f"Bearer {features['token']}"},
        ).json()
        write(OUT / "staff" / "features_permission.json", feat)

        # Cross-tenant denial fixture
        bad = client.get(
            "/api/staff/features-permission",
            headers={"school-code": "DEMOB", "Authorization": f"Bearer {features['token']}"},
        ).json()
        write(OUT / "auth" / "cross_tenant_denied.json", bad)

        denied = client.post(
            "/api/student/login",
            data={"gr_number": "GR001", "password": "wrong", "school_code": "DEMOA"},
        ).json()
        write(OUT / "auth" / "login_failure_bad_password.json", denied)

    print("Golden fixtures captured under", OUT)


if __name__ == "__main__":
    main()
