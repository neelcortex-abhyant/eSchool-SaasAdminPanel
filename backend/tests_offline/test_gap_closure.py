"""Offline tests for four-modules gap closure (no production DB)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.v1.school_academics import AcademicError, LEAVE_STATUS_APPROVED
from app.services.v1.school_erp_payroll import _calc_from_structure, _money


client = TestClient(app)


def _paths() -> set[str]:
    return {getattr(r, "path", "") for r in app.routes}


def test_gap_closure_routes_registered():
    paths = _paths()
    required = [
        "/api/v1/school-admin/fees/send-reminders",
        "/api/v1/school-admin/conversations/attachments/upload",
        "/api/v1/school-admin/messages/{message_id}/attachments",
        "/api/teacher/leave-requests",
        "/api/staff/leave-request",
    ]
    missing = [p for p in required if p not in paths]
    assert missing == [], f"Missing paths: {missing}"


def test_alembic_single_head_0045():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    assert script.get_heads() == ["20261030_0045"]


def test_negative_net_rejected():
    class _Struct:
        basic = 1000

    class _Line:
        def __init__(self, name, kind, amount):
            self.name = name
            self.kind = kind
            self.amount = amount

    lines = [_Line("Ded", "deduction", 5000)]
    try:
        _calc_from_structure(_Struct(), lines, attendance_adjustment=0)
        assert False, "expected negative net rejection"
    except AcademicError as exc:
        assert exc.status_code == 422
        assert "negative" in exc.detail.lower()


def test_payroll_audit_schema_fields():
    from app.schemas.v1.school_admin_mgmt_responses import (
        PayrollAuditEventListOut,
        PayrollAuditEventOut,
    )

    item = PayrollAuditEventOut(
        id=1, run_id=2, actor_user_id=None, action="process", detail_json="{}", created_at=None
    )
    envelope = PayrollAuditEventListOut(items=[item], total=1, page=1, page_size=20)
    assert envelope.items[0].action == "process"


def test_leave_applies_to_staff_only():
    from app.services.v1.school_academics import _assert_leave_type_applies_to

    class _Lt:
        school_id = 1
        deleted_at = None
        applies_to = "staff"
        is_active = 1
        id = 9

    class _Db:
        def get(self, model, pk):
            return _Lt()

        def query(self, model):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None  # not staff

            return _Q()

    # Patch _owned via calling with leave_type that uses _owned - need real path
    # Unit-test the role branching through a thin wrapper mock of owned:
    import app.services.v1.school_academics as academics

    original_owned = academics._owned
    academics._owned = lambda db, model, pk, school_id: _Lt()  # type: ignore
    try:
        try:
            _assert_leave_type_applies_to(_Db(), 1, user_id=99, leave_type_id=9)  # type: ignore
            assert False, "expected applies_to failure"
        except AcademicError as exc:
            assert exc.status_code == 422
            assert "staff" in exc.detail.lower()
    finally:
        academics._owned = original_owned


def test_notification_idempotency_and_no_fcm_stays_queued():
    from app.services.v1 import notification_delivery as nd

    class _School:
        deleted_at = None

    class _Db:
        def __init__(self):
            self._rows = {}
            self._next = 1

        def get(self, model, pk):
            if model.__name__ == "School":
                return _School()
            return self._rows.get(pk)

        def query(self, model):
            outer = self

            class _Q:
                def __init__(self):
                    self._filters = {}

                def filter(self, *a, **k):
                    return self

                def first(self):
                    for row in outer._rows.values():
                        if getattr(row, "idempotency_key", None) == "dup-key":
                            return row
                    return None

                def all(self):
                    return []

                def order_by(self, *a, **k):
                    return self

                def limit(self, *a, **k):
                    return self

            return _Q()

        def add(self, row):
            if getattr(row, "id", None) is None:
                row.id = self._next
                self._next += 1
            self._rows[row.id] = row

        def refresh(self, row):
            return None

        def scalar(self, *a, **k):
            return None

    original_commit = nd._commit
    nd._commit = lambda db: None
    try:
        db = _Db()
        first = nd._enqueue(
            db, 1, title="T", body="B", audience=["all"], idempotency_key="dup-key"  # type: ignore
        )
        second = nd._enqueue(
            db, 1, title="T2", body="B2", audience=["all"], idempotency_key="dup-key"  # type: ignore
        )
        assert first["id"] == second["id"]
        assert second.get("idempotent_replay") is True

        result = nd.attempt_deliver_notification(db, first["id"])  # type: ignore
        assert result["delivery"] == "queued"
    finally:
        nd._commit = original_commit


def test_fcm_delivery_success_with_mock_sender(monkeypatch):
    from app.services.v1 import notification_delivery as nd

    monkeypatch.setattr(
        nd,
        "_firebase_creds_from_env",
        lambda: {
            "project_id": "demo",
            "client_email": "a@b.c",
            "private_key": "unused",
        },
    )
    monkeypatch.setattr(nd, "_google_access_token", lambda creds: "token")
    monkeypatch.setattr(
        nd,
        "_send_fcm_message",
        lambda token, project, message: {"ok": True, "status_code": 200, "body": {}},
    )

    class _User:
        def __init__(self):
            self.id = 5
            self.school_id = 1
            self.fcm_id = "tok-1"
            self.deleted_at = None

    class _Row:
        id = 7
        deleted_at = None
        delivery = "queued"
        school_id = 1
        audience_json = '["all"]'
        title = "Hi"
        body = "Body"
        recipients = 0
        delivered = 0
        failed = 0
        failure_reason = None
        retry_count = 0
        max_retries = 3
        last_attempt_at = None
        updated_at = None

    class _Db:
        def get(self, model, pk):
            if model.__name__ == "Notification":
                return _Row()
            return None

        def query(self, model):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def all(self):
                    if model.__name__ == "User":
                        return [_User()]
                    return []

            return _Q()

    original_commit = nd._commit
    nd._commit = lambda db: None
    try:
        result = nd.attempt_deliver_notification(_Db(), 7)  # type: ignore
        assert result["delivery"] == "sent"
        assert result["delivered"] == 1
    finally:
        nd._commit = original_commit


def test_messaging_attachment_rejects_foreign_storage_key(monkeypatch):
    from app.services.v1 import school_messaging as messaging

    monkeypatch.setattr(messaging, "storage_configured", lambda: True)
    try:
        messaging._validate_attachments_meta(
            [{"original_filename": "a.pdf", "storage_key": "9/1/abc.pdf"}],
            school_id=1,
            uploader_user_id=2,
        )
        assert False, "expected ownership failure"
    except AcademicError as exc:
        assert exc.status_code == 422


def test_messaging_admin_actor_uses_school_admin_id():
    from app.services.v1.school_messaging import ensure_school_admin_actor

    class _User:
        def __init__(self, uid, school_id):
            self.id = uid
            self.school_id = school_id
            self.deleted_at = None
            self.email = "admin@school.test"

    class _School:
        admin_id = 42
        deleted_at = None

    class _Db:
        def get(self, model, pk):
            if model.__name__ == "School":
                return _School()
            if model.__name__ == "User" and pk == 42:
                return _User(42, 1)
            return None

        def query(self, model):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

            return _Q()

    actor = ensure_school_admin_actor(_Db(), 1, email=None)  # type: ignore
    assert actor == 42


def test_leave_decision_records_actor_fields():
    from app.services.v1.school_academics import _record_leave_decision

    row = SimpleNamespace(decided_by_user_id=None, decided_by_v1=None, decided_at=None)
    _record_leave_decision(row, actor_user_id=11, actor_v1="uuid-here")
    assert row.decided_by_user_id == 11
    assert row.decided_by_v1 == "uuid-here"
    assert row.decided_at is not None


def test_unpaid_adj_still_money_safe():
    assert _money(Decimal("1.005")) == 1.01


def test_leave_patch_rejects_status_field():
    """PATCH must not silently ignore status — clients use approve/reject/cancel."""
    from app.services.v1 import school_academics as academics

    row = SimpleNamespace(
        id=10,
        school_id=1,
        status=academics.LEAVE_STATUS_PENDING,
        user_id=5,
        reason="Fever",
        from_date=date.today(),
        to_date=date.today() + timedelta(days=1),
        session_year_id=1,
        leave_type_id=None,
        decided_by_user_id=None,
        decided_by_v1=None,
        decided_at=None,
        updated_at=None,
    )

    original_owned = academics._owned
    original_commit = academics._commit
    academics._owned = lambda db, model, pk, school_id: row  # type: ignore
    academics._commit = lambda db: None
    try:
        try:
            academics.update_leave(SimpleNamespace(), 1, 10, {"status": 1})  # type: ignore
            assert False, "expected 422 for status on PATCH"
        except AcademicError as exc:
            assert exc.status_code == 422
            assert "approve" in exc.detail.lower() or "reject" in exc.detail.lower()
    finally:
        academics._owned = original_owned
        academics._commit = original_commit


def test_leave_approve_reject_cancel_transitions_and_guards():
    from app.services.v1 import school_academics as academics

    def _row(status: int):
        return SimpleNamespace(
            id=11,
            school_id=1,
            status=status,
            user_id=5,
            reason="Trip",
            from_date=date.today(),
            to_date=date.today(),
            session_year_id=1,
            leave_type_id=None,
            decided_by_user_id=None,
            decided_by_v1=None,
            decided_at=None,
            updated_at=None,
        )

    class _Db:
        def get(self, *a, **k):
            return None

        def refresh(self, row):
            return None

        def query(self, *a, **k):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def first(self):
                    return None

                def all(self):
                    return []

            return _Q()

        def add(self, *a, **k):
            return None

    original_owned = academics._owned
    original_commit = academics._commit
    original_overlap = academics._assert_no_leave_overlap
    original_balance = academics._assert_leave_balance_allows
    original_applies = academics._assert_leave_type_applies_to
    original_leave_dict = academics._leave_dict
    academics._commit = lambda db: None
    academics._assert_no_leave_overlap = lambda *a, **k: None
    academics._assert_leave_balance_allows = lambda *a, **k: None
    academics._assert_leave_type_applies_to = lambda *a, **k: None
    academics._leave_dict = lambda db, school_id, row: {
        "id": row.id,
        "status": row.status,
        "decided_by_v1": row.decided_by_v1,
    }

    try:
        pending = _row(academics.LEAVE_STATUS_PENDING)
        academics._owned = lambda db, model, pk, school_id: pending  # type: ignore
        out = academics.approve_leave(_Db(), 1, 11, actor_v1="admin-1")  # type: ignore
        assert pending.status == academics.LEAVE_STATUS_APPROVED
        assert out["action"] == "approved"
        assert pending.decided_by_v1 == "admin-1"

        pending2 = _row(academics.LEAVE_STATUS_PENDING)
        academics._owned = lambda db, model, pk, school_id: pending2  # type: ignore
        out = academics.reject_leave(_Db(), 1, 11, actor_v1="admin-2")  # type: ignore
        assert pending2.status == academics.LEAVE_STATUS_REJECTED
        assert out["action"] == "rejected"

        pending3 = _row(academics.LEAVE_STATUS_PENDING)
        academics._owned = lambda db, model, pk, school_id: pending3  # type: ignore
        out = academics.cancel_leave(_Db(), 1, 11, actor_v1="admin-3")  # type: ignore
        assert pending3.status == academics.LEAVE_STATUS_CANCELLED
        assert pending3.status == 3
        assert out["action"] == "cancelled"

        cancelled = _row(academics.LEAVE_STATUS_CANCELLED)
        academics._owned = lambda db, model, pk, school_id: cancelled  # type: ignore
        try:
            academics.approve_leave(_Db(), 1, 11, actor_v1="x")  # type: ignore
            assert False, "cancelled leave must not be approved"
        except AcademicError as exc:
            assert exc.status_code == 409

        approved = _row(academics.LEAVE_STATUS_APPROVED)
        academics._owned = lambda db, model, pk, school_id: approved  # type: ignore
        try:
            academics.cancel_leave(_Db(), 1, 11)  # type: ignore
            assert False, "approved leave must not cancel via this path"
        except AcademicError as exc:
            assert exc.status_code == 409
    finally:
        academics._owned = original_owned
        academics._commit = original_commit
        academics._assert_no_leave_overlap = original_overlap
        academics._assert_leave_balance_allows = original_balance
        academics._assert_leave_type_applies_to = original_applies
        academics._leave_dict = original_leave_dict


def test_payroll_process_rejects_client_amounts():
    from app.services.v1.school_erp_payroll import process_payroll

    try:
        process_payroll(
            SimpleNamespace(),
            1,
            {"month": "2026-10", "items": [{"net": 999}]},
        )
        assert False, "expected client amount rejection"
    except AcademicError as exc:
        assert exc.status_code == 422
        assert "amount" in exc.detail.lower() or "accepted" in exc.detail.lower()


def test_payroll_mark_paid_transitions():
    from app.services.v1 import school_erp_payroll as payroll

    run = SimpleNamespace(
        id=3,
        school_id=1,
        status="processed",
        period_label="2026-10",
        run_date=date.today(),
        total_amount=1000,
        processed_at=None,
        idempotency_key=None,
        created_at=None,
        updated_at=None,
        deleted_at=None,
    )
    events: list[str] = []

    class _Db:
        def add(self, row):
            events.append(getattr(row, "action", ""))

        def refresh(self, row):
            return None

    original_owned = payroll._owned
    original_commit = payroll._commit
    payroll._owned = lambda db, model, pk, school_id: run  # type: ignore
    payroll._commit = lambda db: None
    try:
        out = payroll.mark_payroll_paid(_Db(), 1, 3, actor_v1="v1-admin")  # type: ignore
        assert run.status == "paid"
        assert out["status"] == "paid"
        assert "mark_paid" in events

        # Idempotent re-mark
        out2 = payroll.mark_payroll_paid(_Db(), 1, 3, actor_v1="v1-admin")  # type: ignore
        assert out2["status"] == "paid"

        draft = SimpleNamespace(
            id=4,
            school_id=1,
            status="draft",
            period_label="2026-11",
            run_date=date.today(),
            total_amount=0,
            processed_at=None,
            idempotency_key=None,
            created_at=None,
            updated_at=None,
            deleted_at=None,
        )
        payroll._owned = lambda db, model, pk, school_id: draft  # type: ignore
        try:
            payroll.mark_payroll_paid(_Db(), 1, 4)  # type: ignore
            assert False, "draft cannot be marked paid"
        except AcademicError as exc:
            assert exc.status_code == 409
    finally:
        payroll._owned = original_owned
        payroll._commit = original_commit


def test_legacy_payroll_run_rejects_client_items():
    from app.services.v1.school_academic_mgmt import create_payroll_run

    try:
        create_payroll_run(
            SimpleNamespace(),
            1,
            {"period_label": "2026-10", "items": [{"net": 1}]},
        )
        assert False, "expected rejection"
    except AcademicError as exc:
        assert exc.status_code == 422


def test_notification_cancel_and_max_retries():
    from app.services.v1 import notification_delivery as nd

    class _Row:
        def __init__(self, delivery="queued"):
            self.id = 9
            self.school_id = 1
            self.deleted_at = None
            self.delivery = delivery
            self.updated_at = None
            self.retry_count = 3
            self.max_retries = 3
            self.audience_json = '["all"]'
            self.title = "T"
            self.body = "B"
            self.recipients = 0
            self.delivered = 0
            self.failed = 0
            self.failure_reason = None
            self.last_attempt_at = None

    failed_row = _Row("failed")

    class _Db:
        def get(self, model, pk):
            return failed_row

    original_commit = nd._commit
    original_creds = nd._firebase_creds_from_env
    nd._commit = lambda db: None
    nd._firebase_creds_from_env = lambda: {
        "project_id": "p",
        "client_email": "a@b.c",
        "private_key": "k",
    }
    try:
        result = nd.attempt_deliver_notification(_Db(), 9)  # type: ignore
        assert result["delivery"] == "failed"
        assert result.get("reason") == "max_retries"

        queued = _Row("queued")
        queued.status = 1
        queued.title = "T"
        queued.body = "B"
        queued.audience_json = '["all"]'
        queued.recipients = 0
        queued.delivered = 0
        queued.failed = 0
        queued.failure_reason = None

        class _Db2:
            def get(self, model, pk):
                return queued

            def refresh(self, row):
                return None

        cancelled = nd.cancel_notification(_Db2(), 1, 9)  # type: ignore
        assert cancelled["delivery"] == "cancelled"

        sent = _Row("sent")
        sent.status = 1
        sent.title = "T"
        sent.body = "B"
        sent.audience_json = '["all"]'
        sent.recipients = 1
        sent.delivered = 1
        sent.failed = 0
        sent.failure_reason = None

        class _Db3:
            def get(self, model, pk):
                return sent

            def refresh(self, row):
                return None

        try:
            nd.cancel_notification(_Db3(), 1, 9)  # type: ignore
            assert False, "cannot cancel sent"
        except AcademicError as exc:
            assert exc.status_code == 409
    finally:
        nd._commit = original_commit
        nd._firebase_creds_from_env = original_creds


def test_notification_failed_delivery_with_mock_sender(monkeypatch):
    from app.services.v1 import notification_delivery as nd

    monkeypatch.setattr(
        nd,
        "_firebase_creds_from_env",
        lambda: {"project_id": "demo", "client_email": "a@b.c", "private_key": "x"},
    )
    monkeypatch.setattr(nd, "_google_access_token", lambda creds: "token")
    monkeypatch.setattr(
        nd,
        "_send_fcm_message",
        lambda token, project, message: {"ok": False, "status_code": 500, "body": {"error": "boom"}},
    )

    class _User:
        id = 5
        school_id = 1
        fcm_id = "tok-1"
        deleted_at = None

    class _Row:
        id = 8
        deleted_at = None
        delivery = "queued"
        school_id = 1
        audience_json = '["all"]'
        title = "Hi"
        body = "Body"
        recipients = 0
        delivered = 0
        failed = 0
        failure_reason = None
        retry_count = 2  # one attempt left → stays queued; set to max to fail
        max_retries = 3
        last_attempt_at = None
        updated_at = None

    class _Db:
        def get(self, model, pk):
            return _Row()

        def query(self, model):
            class _Q:
                def filter(self, *a, **k):
                    return self

                def all(self):
                    return [_User()] if model.__name__ == "User" else []

            return _Q()

    original_commit = nd._commit
    nd._commit = lambda db: None
    try:
        # retry_count 2 + 1 = 3 == max → failed
        result = nd.attempt_deliver_notification(_Db(), 8)  # type: ignore
        assert result["delivery"] == "failed"
        assert result["ok"] is False
    finally:
        nd._commit = original_commit


def test_messaging_attachment_aliases_and_url_key_rejected(monkeypatch):
    from app.services.v1 import school_messaging as messaging

    monkeypatch.setattr(messaging, "storage_configured", lambda: True)
    try:
        messaging._validate_attachments_meta(
            [
                {
                    "original_filename": "a.pdf",
                    "storage_key": "https://evil.example/file.pdf",
                }
            ],
            school_id=1,
            uploader_user_id=2,
        )
        assert False, "URL storage_key must be rejected"
    except AcademicError as exc:
        assert exc.status_code == 422

    parsed = messaging._parse_attachments(
        '[{"original_filename":"doc.pdf","content_type":"application/pdf",'
        '"size_bytes":12,"storage_key":"1/2/k.pdf"}]',
        message_id=55,
    )
    assert len(parsed) == 1
    assert parsed[0]["name"] == "doc.pdf"
    assert parsed[0]["size"] == 12
    assert parsed[0]["original_filename"] == "doc.pdf"
    assert "download_path" in parsed[0]
    assert "/messages/55/attachments" in parsed[0]["download_path"]
    assert not str(parsed[0].get("download_path", "")).startswith("http")


def test_leave_status_cancelled_constant_is_three():
    from app.services.v1.school_academics import LEAVE_STATUS_CANCELLED, LEAVE_STATUS_PENDING

    assert LEAVE_STATUS_CANCELLED == 3
    assert LEAVE_STATUS_PENDING == 0
    assert LEAVE_STATUS_CANCELLED != LEAVE_STATUS_PENDING
