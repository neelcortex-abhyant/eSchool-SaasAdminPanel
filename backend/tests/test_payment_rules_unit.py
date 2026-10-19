"""Payment state rules, webhook parsing, and invoice PDF headers. Does not open a database or call Razorpay."""

from __future__ import annotations

import json
from datetime import date, datetime
from types import SimpleNamespace

import pytest
import razorpay
import requests
from razorpay.errors import BadRequestError

from app.api.v1.super_admin.invoices import invoice_pdf_response
from app.models.tables import (
    PAYMENT_STATUS_AUTHORIZED,
    PAYMENT_STATUS_CAPTURED,
    PAYMENT_STATUS_CREATED,
    PAYMENT_STATUS_FAILED,
    PAYMENT_STATUS_REFUNDED,
)
from app.services.v1 import payment_verification_service as rules
from app.services.v1.invoice_pdf import invoice_filename
from app.services.v1.payment_order_service import PaymentOrderError, _require_reusable
from app.services.v1.razorpay_client import RazorpayPaymentFetcher


class _NoOwnerSession:
    """Answers the payment-id owner lookup in _bind_payment_id."""

    def __init__(self, owner: int | None = None):
        self.owner = owner

    def scalar(self, _statement):
        return self.owner


def _row(status: int, payment_id: str | None = None, **extra) -> SimpleNamespace:
    values = {
        "id": 1,
        "bill_id": 10,
        "school_id": 5,
        "status": status,
        "gateway_payment_id": payment_id,
        "gateway_order_id": "order_1",
        "amount_paise": 249900,
        "currency": "INR",
        "updated_at": None,
    }
    values.update(extra)
    return SimpleNamespace(**values)


def _raw(payload: dict) -> bytes:
    return json.dumps(payload).encode()


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        (PAYMENT_STATUS_CREATED, PAYMENT_STATUS_AUTHORIZED, PAYMENT_STATUS_AUTHORIZED),
        (PAYMENT_STATUS_CREATED, PAYMENT_STATUS_CAPTURED, PAYMENT_STATUS_CAPTURED),
        (PAYMENT_STATUS_FAILED, PAYMENT_STATUS_CAPTURED, PAYMENT_STATUS_CAPTURED),
        (PAYMENT_STATUS_FAILED, PAYMENT_STATUS_AUTHORIZED, PAYMENT_STATUS_AUTHORIZED),
        (PAYMENT_STATUS_AUTHORIZED, PAYMENT_STATUS_FAILED, PAYMENT_STATUS_FAILED),
        (PAYMENT_STATUS_CAPTURED, PAYMENT_STATUS_FAILED, None),
        (PAYMENT_STATUS_CAPTURED, PAYMENT_STATUS_AUTHORIZED, None),
        (PAYMENT_STATUS_REFUNDED, PAYMENT_STATUS_CAPTURED, None),
        (PAYMENT_STATUS_AUTHORIZED, None, PAYMENT_STATUS_AUTHORIZED),
    ],
)
def test_next_status_table(current, target, expected):
    assert rules._next_status(current, target) == expected


def test_failed_order_moves_to_authorized_only_for_a_new_payment():
    late = _row(PAYMENT_STATUS_FAILED, "pay_1")
    assert rules._transition(late, PAYMENT_STATUS_AUTHORIZED, rebound=False) is False
    assert late.status == PAYMENT_STATUS_FAILED
    retry = _row(PAYMENT_STATUS_FAILED, "pay_2")
    assert rules._transition(retry, PAYMENT_STATUS_AUTHORIZED, rebound=True) is True
    assert retry.status == PAYMENT_STATUS_AUTHORIZED


def test_bind_payment_id_rules():
    db = _NoOwnerSession()
    fresh = _row(PAYMENT_STATUS_CREATED)
    assert rules._bind_payment_id(db, fresh, "pay_1", PAYMENT_STATUS_AUTHORIZED) == rules._BOUND
    assert fresh.gateway_payment_id == "pay_1"
    assert rules._bind_payment_id(db, fresh, "pay_1", PAYMENT_STATUS_CAPTURED) == rules._SAME

    failed = _row(PAYMENT_STATUS_FAILED, "pay_old")
    assert rules._bind_payment_id(db, failed, "pay_new", PAYMENT_STATUS_AUTHORIZED) == rules._BOUND
    assert failed.gateway_payment_id == "pay_new"

    authorized = _row(PAYMENT_STATUS_AUTHORIZED, "pay_a")
    assert rules._bind_payment_id(db, authorized, "pay_b", PAYMENT_STATUS_FAILED) == rules._STALE
    assert authorized.gateway_payment_id == "pay_a"
    assert rules._bind_payment_id(db, authorized, "pay_b", PAYMENT_STATUS_CAPTURED) == rules._BOUND

    captured = _row(PAYMENT_STATUS_CAPTURED, "pay_c")
    assert rules._bind_payment_id(db, captured, "pay_d", PAYMENT_STATUS_FAILED) == rules._STALE
    with pytest.raises(rules._PaymentConflict):
        rules._bind_payment_id(db, captured, "pay_d", PAYMENT_STATUS_CAPTURED)

    with pytest.raises(rules._PaymentConflict):
        rules._bind_payment_id(_NoOwnerSession(owner=99), _row(PAYMENT_STATUS_CREATED), "pay_x", PAYMENT_STATUS_CAPTURED)


def test_parse_payment_event_accepts_any_upper_case_currency_code():
    entity = {"id": "pay_1", "order_id": "order_1", "amount": 100, "currency": "USD"}
    event = rules._parse_event(_raw({"event": "payment.captured", "payload": {"payment": {"entity": entity}}}), "evt_1")
    assert event.kind == "payment"
    assert event.currency == "USD"
    for currency in ("usd", "RUPEE", 1, None):
        bad = {**entity, "currency": currency}
        with pytest.raises(PaymentOrderError):
            rules._parse_event(_raw({"event": "payment.captured", "payload": {"payment": {"entity": bad}}}), "evt_2")


def test_parse_refund_and_unknown_events():
    refund = rules._parse_event(
        _raw(
            {
                "event": "refund.processed",
                "payload": {
                    "refund": {"entity": {"id": "rfnd_1", "payment_id": "pay_1", "amount": 500, "currency": "INR"}},
                    "payment": {"entity": {"id": "pay_1", "order_id": "order_1", "amount_refunded": 249900}},
                },
            }
        ),
        "evt_refund",
    )
    assert refund.kind == "refund"
    assert refund.payment_id == "pay_1"
    assert refund.order_id == "order_1"
    assert refund.amount == 500
    assert refund.amount_refunded == 249900
    with pytest.raises(PaymentOrderError):
        rules._parse_event(_raw({"event": "refund.processed", "payload": {}}), "evt_bad_refund")
    other = rules._parse_event(_raw({"event": "order.paid", "payload": {}}), "evt_other")
    assert other.kind == "other"
    with pytest.raises(PaymentOrderError):
        rules._parse_event(b"not json", "evt_bad")


def test_remote_payment_must_match_order_amount_and_currency():
    row = _row(PAYMENT_STATUS_CREATED)
    good = {"id": "pay_1", "order_id": "order_1", "amount": 249900, "currency": "INR", "status": "captured"}
    assert rules._remote_matches(good, row, "order_1", "pay_1") is True
    assert rules._remote_matches({**good, "amount": 1}, row, "order_1", "pay_1") is False
    assert rules._remote_matches({**good, "amount": "249900"}, row, "order_1", "pay_1") is False
    assert rules._remote_matches({**good, "currency": "USD"}, row, "order_1", "pay_1") is False
    assert rules._remote_matches({**good, "order_id": "order_2"}, row, "order_1", "pay_1") is False
    assert rules._remote_matches(good, row, "order_1", "pay_2") is False


def test_unreachable_fetcher_is_treated_as_no_gateway_answer():
    class Broken:
        def fetch_payment(self, payment_id):
            raise RuntimeError("down")

    assert rules._fetch_remote(Broken(), "pay_1") is None


def test_open_order_reuse_rules():
    bill = SimpleNamespace(id=10, school_id=5)
    _require_reusable(_row(PAYMENT_STATUS_CREATED), bill, 249900, "INR")
    _require_reusable(_row(PAYMENT_STATUS_FAILED), bill, 249900, "INR")
    for status, detail in (
        (PAYMENT_STATUS_CAPTURED, "Bill already has a captured payment"),
        (PAYMENT_STATUS_AUTHORIZED, "A payment for this bill is awaiting capture"),
    ):
        with pytest.raises(PaymentOrderError) as caught:
            _require_reusable(_row(status), bill, 249900, "INR")
        assert caught.value.status_code == 409
        assert caught.value.detail == detail
    with pytest.raises(PaymentOrderError) as changed:
        _require_reusable(_row(PAYMENT_STATUS_CREATED), bill, 100, "INR")
    assert changed.value.status_code == 409


def test_payment_fetcher_returns_none_on_gateway_errors(monkeypatch):
    outcomes: list = []

    class FakePayment:
        def fetch(self, payment_id, **kwargs):
            result = outcomes.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    class FakeClient:
        def __init__(self, auth=None, **kwargs):
            self.payment = FakePayment()

        def enable_retry(self, enabled=False):
            assert enabled is False

    monkeypatch.setattr(razorpay, "Client", FakeClient)
    fetcher = RazorpayPaymentFetcher("rzp_test_unit", "unit-secret")
    outcomes.extend(
        [
            {"id": "pay_1", "status": "captured"},
            BadRequestError("nope"),
            requests.Timeout("slow"),
            "not a dict",
        ]
    )
    assert fetcher.fetch_payment("pay_1") == {"id": "pay_1", "status": "captured"}
    assert fetcher.fetch_payment("pay_1") is None
    assert fetcher.fetch_payment("pay_1") is None
    assert fetcher.fetch_payment("pay_1") is None


def _invoice(**overrides) -> SimpleNamespace:
    values = {
        "invoice_number": "SUB-2026-000001",
        "issued_at": datetime(2026, 10, 19, 10, 0, 0),
        "gateway": "razorpay",
        "gateway_order_id": "order_1",
        "gateway_payment_id": "pay_1",
        "currency": "INR",
        "amount_paise": 249900,
        "tax_label": None,
        "tax_rate_percent": None,
        "tax_amount_paise": None,
        "total_amount_paise": 249900,
        "school_name": "Unit School",
        "school_address": "1 Road",
        "school_email": "unit@eschool.com",
        "school_phone": "9000000000",
        "plan_name": "Unit Plan",
        "plan_description": None,
        "cycle": "monthly",
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 11, 1),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_invoice_pdf_response_headers():
    response = invoice_pdf_response(_invoice())
    assert response.media_type == "application/pdf"
    assert response.headers["content-disposition"] == 'attachment; filename="SUB-2026-000001.pdf"'
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.body.startswith(b"%PDF")


def test_invoice_filename_strips_unsafe_characters():
    assert invoice_filename('SUB-2026-000001"; x=../../a') == "SUB-2026-000001xa.pdf"
    assert invoice_filename("") == "invoice.pdf"
