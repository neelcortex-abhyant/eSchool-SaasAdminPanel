"""Offline tests for the four School Admin modules completion wave."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.v1.school_erp_payroll import _calc_from_structure, _money


client = TestClient(app)


def _paths() -> set[str]:
    return {getattr(r, "path", "") for r in app.routes}


def test_openapi_registers_four_module_paths():
    paths = _paths()
    required = [
        "/api/v1/school-admin/academics/leaves/{row_id}/approve",
        "/api/v1/school-admin/academics/leaves/{row_id}/reject",
        "/api/v1/school-admin/academics/leaves/{row_id}/cancel",
        "/api/v1/school-admin/payroll-runs/{run_id}/mark-paid",
        "/api/v1/school-admin/payroll/audit-events",
        "/api/v1/school-admin/payroll/preview",
        "/api/v1/school-admin/notifications/{row_id}",
        "/api/v1/school-admin/notifications/{row_id}/cancel",
        "/api/v1/school-admin/conversations/unread-count",
        "/api/teacher/conversations/unread-count",
    ]
    missing = [p for p in required if p not in paths]
    assert missing == [], f"Missing paths: {missing}"


def test_money_quantize_two_dp():
    assert _money(10.005) == 10.01
    assert _money("10.004") == 10.00
    assert _money(Decimal("1.235")) == 1.24


def test_payroll_unpaid_leave_adjustment_formula():
    class _Struct:
        basic = 30000

    class _Line:
        def __init__(self, name, kind, amount):
            self.name = name
            self.kind = kind
            self.amount = amount

    lines = [_Line("HRA", "earning", 0), _Line("PF", "deduction", 3000)]
    base = _calc_from_structure(_Struct(), lines, attendance_adjustment=0)
    assert base["gross"] == 30000
    # 2 unpaid days of 30 working days → -(30000/30)*2 = -2000
    adj = _money(-(Decimal(str(base["gross"])) / Decimal("30") * Decimal("2")))
    calc = _calc_from_structure(_Struct(), lines, attendance_adjustment=adj)
    assert calc["attendance_adjustment"] == -2000.0
    assert calc["net"] == 25000.0


def test_attendance_status_normalize():
    from app.services.v1.school_academic_mgmt import normalize_staff_attendance_status

    assert normalize_staff_attendance_status("present") == "present"
    assert normalize_staff_attendance_status("HALF-DAY") == "half_day"
    assert normalize_staff_attendance_status("late") == "late"
    try:
        normalize_staff_attendance_status("weird")
        assert False, "expected error"
    except Exception as exc:
        assert getattr(exc, "status_code", None) in (400, 422) or "status" in str(exc).lower()


def test_portal_audience_filter():
    from app.api.student_reads import _audience_matches

    assert _audience_matches(None, "students") is True
    assert _audience_matches('["all"]', "parents") is True
    assert _audience_matches('["students"]', "students") is True
    assert _audience_matches('["students"]', "parents") is False
    assert _audience_matches('["parents","teachers"]', "parents") is True


def test_notification_delivery_stays_queued_without_fcm():
    from app.services.v1.notification_delivery import attempt_deliver_notification

    class _Db:
        def get(self, model, pk):
            return SimpleNamespace(
                id=pk,
                deleted_at=None,
                delivery="queued",
                school_id=1,
                audience_json='["all"]',
                recipients=0,
                failure_reason=None,
                updated_at=None,
            )

        def query(self, *a, **k):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def all(self):
                    return []

            return _Q()

        def commit(self):
            return None

        def scalar(self, *a, **k):
            return None

    # Patch commit path used inside attempt_deliver
    import app.services.v1.notification_delivery as nd

    original_commit = nd._commit
    nd._commit = lambda db: None
    try:
        result = attempt_deliver_notification(_Db(), 1)  # type: ignore[arg-type]
        assert result["delivery"] == "queued"
    finally:
        nd._commit = original_commit


def test_messaging_attachments_rejected_without_storage(monkeypatch):
    from app.services.v1 import school_messaging as messaging

    monkeypatch.setattr(messaging, "storage_configured", lambda: False)
    try:
        messaging._validate_attachments_meta(
            [{"original_filename": "a.pdf", "storage_key": "1/2/k1"}],
            school_id=1,
            uploader_user_id=2,
        )
        assert False, "expected 503"
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 503


def test_messaging_admin_ensure_creates_or_uses_school_admin():
    from app.services.v1.school_messaging import ensure_school_admin_actor

    class _School:
        admin_id = 77

    class _User:
        id = 77
        school_id = 1
        deleted_at = None

    class _Db:
        def get(self, model, pk):
            if getattr(model, "__name__", "") == "School":
                return _School()
            if getattr(model, "__name__", "") == "User" and pk == 77:
                return _User()
            return None

        def query(self, *a, **k):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            return _Q()

    assert ensure_school_admin_actor(_Db(), 1) == 77  # type: ignore[arg-type]


def test_alembic_single_head_follows_0045():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["20261030_0045"]


def test_leave_status_constants():
    from app.services.v1.school_academics import (
        LEAVE_STATUS_APPROVED,
        LEAVE_STATUS_CANCELLED,
        LEAVE_STATUS_PENDING,
        LEAVE_STATUS_REJECTED,
    )

    assert LEAVE_STATUS_PENDING == 0
    assert LEAVE_STATUS_APPROVED == 1
    assert LEAVE_STATUS_REJECTED == 2
    assert LEAVE_STATUS_CANCELLED == 3
