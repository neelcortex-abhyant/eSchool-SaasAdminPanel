"""OpenAPI / route registration for School Admin settings (noconftest-friendly)."""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def test_school_admin_settings_routes_registered_on_app():
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    for path in (
        "/api/v1/school-admin/content/{slug}",
        "/api/v1/school-admin/faqs",
        "/api/v1/school-admin/leave-settings",
        "/api/v1/school-admin/online-exam-terms",
        "/api/v1/school-admin/email-templates",
        "/api/v1/school-admin/whatsapp-settings",
        "/api/v1/school-admin/payment-gateway-settings",
        "/api/v1/school-admin/contact-inquiries",
        "/api/v1/school-admin/support-tickets",
        "/api/v1/super-admin/backups",
    ):
        assert path in route_paths, path


def test_public_contact_and_backup_restore_registered():
    route_paths = {r.path for r in app.routes if isinstance(r, APIRoute)}
    assert "/api/v1/public/schools/{code}/contact-inquiries" in route_paths
    assert "/api/v1/super-admin/backups/{backup_id}/restore" in route_paths

    content = [
        r
        for r in app.routes
        if isinstance(r, APIRoute) and r.path == "/api/v1/school-admin/content/{slug}"
    ]
    methods = set()
    for r in content:
        methods.update(r.methods or [])
    assert "GET" in methods
    assert "PUT" in methods
