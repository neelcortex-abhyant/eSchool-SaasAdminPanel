"""DB-free: School Admin password routes are registered (no duplicate services)."""

from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def test_auth_password_routes_registered_once():
    paths = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if isinstance(route, APIRoute)
    }
    assert ("/api/v1/auth/forgot-password", ("POST",)) in paths
    assert ("/api/v1/auth/reset-password", ("POST",)) in paths
    assert ("/api/v1/auth/change-password", ("POST",)) in paths
    # No duplicate School Admin-only password routers.
    school_admin_password = [
        path for path, _methods in paths if "school-admin" in path and "password" in path
    ]
    assert school_admin_password == []
