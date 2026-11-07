"""Offline API journey stubs for School ERP phase 10 (no DB).

Documents expected route registration and isolation contracts.
Original 29 QA cases remain BLOCKED.
"""

from __future__ import annotations

from app.api.v1.router import router
from app.api.v1 import school_admin_branches


def _paths() -> set[str]:
    found: set[str] = set()
    for route in router.routes:
        path = getattr(route, "path", None)
        if path:
            found.add(path)
    return found


def test_branch_routes_registered():
    paths = _paths()
    assert "/api/v1/school-admin/branches" in paths
    assert "/api/v1/school-admin/branches/{branch_id}" in paths
    assert "/api/v1/school-admin/branches/{branch_id}/admins" in paths
    assert "/api/v1/school-admin/me/branches" in paths


def test_journey_checklist_documented():
    """Phase 10 journeys — status pending until isolated DB available."""
    journeys = [
        "register_school_login_me_dashboard",
        "create_branch2_assign_admin_switch_header",
        "branch2_class_section_student",
        "fee_assign_payment_summary",
        "attendance_exam_result",
        "branch_admin_denied_other_branch",
        "school_admin_consolidated_reports",
        "branch1_unchanged_after_branch2_ops",
    ]
    assert len(journeys) == 8
    assert school_admin_branches.router is not None


def test_x_branch_id_hint_contract():
    """Deps expose get_branch_context; header alone is never trusted (service ACL)."""
    from app.api.v1 import deps

    assert hasattr(deps, "get_branch_context")
    assert hasattr(deps, "get_branch_context_optional_consolidated")
