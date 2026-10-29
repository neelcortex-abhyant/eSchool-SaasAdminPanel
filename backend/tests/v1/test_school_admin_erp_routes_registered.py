"""OpenAPI / route registration for School Admin ERP (noconftest-friendly)."""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def test_school_admin_erp_routes_registered_on_app():
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    for path in (
        "/api/v1/school-admin/report-cards/{report_id}/pdf",
        "/api/v1/school-admin/fee-structures/{structure_id}/installments",
        "/api/v1/school-admin/fee-payments/{payment_id}/receipt/pdf",
        "/api/v1/school-admin/fee-payments/{payment_id}/cancel",
        "/api/v1/school-admin/fees/collection-report",
        "/api/v1/school-admin/transport-trips",
        "/api/v1/school-admin/transport-trips/{trip_id}/gps",
        "/api/v1/school-admin/transport/reports/trips",
    ):
        assert path in route_paths, path


def test_staff_and_portal_erp_routes_registered():
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/staff/transport/my-trips" in route_paths
    assert "/api/staff/transport/trips/{trip_id}/gps" in route_paths
    assert "/api/student/report-cards/{report_id}/pdf" in route_paths
    assert "/api/student/fees/balance" in route_paths
    assert "/api/parent/children/{student_id}/fees/balance" in route_paths
    assert "/api/parent/children/{student_id}/transport/live" in route_paths

    installments = [
        r
        for r in app.routes
        if isinstance(r, APIRoute)
        and r.path == "/api/v1/school-admin/fee-structures/{structure_id}/installments"
    ]
    methods = set()
    for r in installments:
        methods.update(r.methods or [])
    assert "GET" in methods
    assert "PUT" in methods
