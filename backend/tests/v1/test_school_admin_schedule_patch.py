"""Offline exam schedule PATCH/DELETE route registration (and related mgmt mounts).

Runs with v1_client when DB available; OpenAPI path check needs only app import.
"""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app

SCH = "/api/v1/school-admin/offline-exam-schedules"


def test_offline_exam_schedule_patch_delete_routes_registered():
    schedule_routes = [
        r for r in app.routes if isinstance(r, APIRoute) and r.path == f"{SCH}/{{schedule_id}}"
    ]
    methods = set()
    for r in schedule_routes:
        methods.update(r.methods or [])
    assert "PATCH" in methods
    assert "DELETE" in methods


def test_academic_mgmt_wave_routes_registered_on_app():
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    for path in (
        "/api/v1/school-admin/grading-scales",
        "/api/v1/school-admin/report-cards",
        "/api/v1/school-admin/question-bank",
        "/api/v1/school-admin/fee-types",
        "/api/v1/school-admin/fees/collect",
        "/api/v1/school-admin/fees/outstanding",
        "/api/v1/school-admin/subscription/plans",
    ):
        assert path in route_paths, path
