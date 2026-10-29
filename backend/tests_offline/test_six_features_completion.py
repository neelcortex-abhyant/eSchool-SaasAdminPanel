"""Offline tests for the six School Admin feature completion wave."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.services.v1.school_erp_payroll import _calc_from_structure
from app.services.v1.school_erp_transport import gps_freshness


client = TestClient(app)


def _paths() -> set[str]:
    return {getattr(r, "path", "") for r in app.routes}


def test_openapi_registers_six_feature_paths():
    paths = _paths()
    required = [
        "/api/v1/school-admin/transport/vehicle-locations",
        "/api/v1/school-admin/transport-trips/{trip_id}",
        "/api/v1/school-admin/leave-types",
        "/api/v1/school-admin/leave-balances",
        "/api/v1/school-admin/announcements/{row_id}",
        "/api/v1/school-admin/salary-structures",
        "/api/v1/school-admin/salary-assignments",
        "/api/v1/school-admin/payroll/preview",
        "/api/v1/school-admin/payroll/process",
        "/api/v1/school-admin/payroll/summary",
        "/api/v1/school-admin/payslips",
        "/api/v1/school-admin/payslips/{row_id}/pdf",
        "/api/v1/school-admin/messaging/policy",
        "/api/v1/school-admin/conversations",
        "/api/v1/school-admin/messages/{message_id}",
        "/api/v1/school-admin/certificates/issue-staff",
        "/api/v1/school-admin/certificates/{row_id}/pdf",
        "/api/v1/school-admin/certificates/{row_id}/revoke",
        "/api/v1/public/certificates/verify/{token}",
        "/api/teacher/conversations",
        "/api/parent/conversations",
    ]
    missing = [p for p in required if p not in paths]
    assert missing == [], f"Missing paths: {missing}"


def test_gps_freshness_thresholds():
    now = datetime(2026, 10, 29, 12, 0, 0)
    assert gps_freshness(now, now=now) == "live"
    assert gps_freshness(now - timedelta(minutes=6), now=now) == "stale"
    assert gps_freshness(now - timedelta(minutes=31), now=now) == "offline"
    assert gps_freshness(None, now=now) == "missing"


def test_payroll_formula_deterministic():
    class _Struct:
        basic = 30000

    class _Line:
        def __init__(self, name, kind, amount):
            self.name = name
            self.kind = kind
            self.amount = amount

    lines = [
        _Line("HRA", "earning", 8000),
        _Line("PF", "deduction", 1800),
        _Line("Tax", "deduction", 2000),
    ]
    calc = _calc_from_structure(_Struct(), lines)
    assert calc["gross"] == 38000
    assert calc["deductions_total"] == 3800
    assert calc["attendance_adjustment"] == 0
    assert calc["net"] == 34200


def test_announcement_lazy_publish_helper():
    from app.services.v1.school_academic_mgmt import _lazy_publish_announcement

    class _Ann:
        status = "scheduled"
        publish_at = datetime.now() - timedelta(minutes=1)
        published_at = None
        updated_at = None

    row = _Ann()
    _lazy_publish_announcement(db=None, row=row)  # type: ignore[arg-type]
    assert row.status == "published"
    assert row.published_at is not None


def test_certificate_verify_path_is_opaque():
    from app.services.v1.school_academic_mgmt import _certificate_verify_path, _new_verification_token

    token = _new_verification_token()
    url = _certificate_verify_path(token)
    assert token in url
    assert "/api/v1/public/certificates/verify/" in url
    assert "student" not in url.lower()
    assert "staff" not in url.lower()


def test_messaging_policy_defaults():
    from app.services.v1.school_messaging import policy_item

    item = policy_item(None, school_id=7)
    assert item["can_view"] is True
    assert item["can_send"] is True
    assert item["can_moderate"] is True
    assert item["poll_seconds"] == 15


def test_alembic_single_head_0043():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["20261029_0043"]
