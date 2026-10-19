"""Order conversion and Razorpay configuration checks. Does not open a database or call Razorpay."""

from __future__ import annotations

import pytest
import requests
import razorpay
from pydantic import SecretStr
from razorpay.errors import BadRequestError

from app.core.config import Settings
from app.services.v1.payment_order_service import PaymentOrderError, rupees_to_paise
from app.services.v1.razorpay_client import RazorpayOrderGateway, charge_currency, validate_razorpay_credentials


def _settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "razorpay_currency": "INR",
        "razorpay_key_id": "rzp_test_unit",
        "razorpay_key_secret": SecretStr("unit-secret"),
        "razorpay_webhook_secret": SecretStr("unit-webhook"),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_rupees_to_paise_rounds_half_up():
    assert rupees_to_paise(10.125) == 1013
    assert rupees_to_paise(19.99) == 1999
    assert rupees_to_paise(1) == 100


def test_rupees_to_paise_rejects_zero_negative_and_overflow():
    with pytest.raises(ValueError):
        rupees_to_paise(0)
    with pytest.raises(ValueError):
        rupees_to_paise(-1)
    with pytest.raises(ValueError):
        rupees_to_paise(10000000000)


def test_missing_credentials_raise_without_echoing_values():
    settings = _settings(razorpay_key_id="", razorpay_key_secret=SecretStr(""))
    with pytest.raises(PaymentOrderError) as caught:
        validate_razorpay_credentials(settings)
    assert caught.value.status_code == 503
    assert caught.value.detail == "Payment configuration is missing"
    assert "unit-webhook" not in caught.value.detail


def test_test_and_live_keys_stay_in_their_environments():
    with pytest.raises(PaymentOrderError) as live_in_test:
        validate_razorpay_credentials(_settings(razorpay_key_id="rzp_live_unit"))
    assert live_in_test.value.status_code == 503
    assert "rzp_live_unit" not in live_in_test.value.detail
    with pytest.raises(PaymentOrderError) as test_in_production:
        validate_razorpay_credentials(_settings(app_env="production", razorpay_key_id="rzp_test_unit"))
    assert test_in_production.value.status_code == 503
    production = validate_razorpay_credentials(
        _settings(app_env="production", razorpay_key_id="rzp_live_unit")
    )
    assert production[0] == "rzp_live_unit"
    assert production[1] == "unit-secret"
    assert "unit-webhook" not in production


def test_only_inr_is_accepted():
    assert charge_currency(_settings()) == "INR"
    with pytest.raises(PaymentOrderError) as caught:
        charge_currency(_settings(razorpay_currency="USD"))
    assert caught.value.status_code == 422


def test_gateway_wrapper_disables_retry_and_hides_rejection_text(monkeypatch):
    seen = {}

    class FakeOrder:
        def create(self, data, **kwargs):
            seen["data"] = data
            raise BadRequestError("unit-secret")

    class FakeClient:
        def __init__(self, auth=None, **kwargs):
            self.order = FakeOrder()

        def enable_retry(self, enabled=False):
            seen["retry"] = enabled

    monkeypatch.setattr(razorpay, "Client", FakeClient)
    gateway = RazorpayOrderGateway("rzp_test_unit", "unit-secret")
    with pytest.raises(PaymentOrderError) as caught:
        gateway.create_order(amount_paise=1013, currency="INR", receipt="bill-1", notes={"bill_id": "1"})
    assert seen["retry"] is False
    assert seen["data"]["amount"] == 1013
    assert caught.value.status_code == 502
    assert caught.value.outcome_unknown is False
    assert "unit-secret" not in caught.value.detail


def test_gateway_timeout_is_an_unknown_outcome(monkeypatch):
    class FakeOrder:
        def create(self, data, **kwargs):
            raise requests.Timeout("timed out")

    class FakeClient:
        def __init__(self, auth=None, **kwargs):
            self.order = FakeOrder()

        def enable_retry(self, enabled=False):
            return None

    monkeypatch.setattr(razorpay, "Client", FakeClient)
    gateway = RazorpayOrderGateway("rzp_test_unit", "unit-secret")
    with pytest.raises(PaymentOrderError) as caught:
        gateway.create_order(amount_paise=100, currency="INR", receipt="bill-1", notes={"bill_id": "1"})
    assert caught.value.status_code == 504
    assert caught.value.outcome_unknown is True
