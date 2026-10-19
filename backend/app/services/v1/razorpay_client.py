"""Razorpay order and payment client. Does not log credentials or enable SDK retries."""

from __future__ import annotations

import requests
import razorpay
from razorpay.errors import BadRequestError, GatewayError, ServerError, SignatureVerificationError

from app.core.config import Settings
from app.services.v1.payment_order_service import PaymentOrderError


def validate_razorpay_credentials(settings: Settings) -> tuple[str, str]:
    """Return the key id and key secret, or raise when they cannot be used.

    The webhook secret is not returned. Production accepts an ``rzp_live_`` key
    id. Every other environment accepts an ``rzp_test_`` key id.
    """
    key_id = (settings.razorpay_key_id or "").strip()
    key_secret = settings.razorpay_key_secret.get_secret_value().strip()
    if not key_id or not key_secret:
        raise PaymentOrderError("Payment configuration is missing", status_code=503)
    live = key_id.startswith("rzp_live_")
    test = key_id.startswith("rzp_test_")
    if settings.app_env == "production":
        if not live:
            raise PaymentOrderError(
                "Payment configuration does not match this environment",
                status_code=503,
            )
    elif not test:
        raise PaymentOrderError(
            "Payment configuration does not match this environment",
            status_code=503,
        )
    return key_id, key_secret


def webhook_secret(settings: Settings) -> str:
    """Return the webhook secret. Order creation does not call this."""
    secret = settings.razorpay_webhook_secret.get_secret_value().strip()
    if not secret:
        raise PaymentOrderError("Payment configuration is missing", status_code=503)
    return secret


def verify_checkout_signature(
    *,
    key_id: str,
    key_secret: str,
    order_id: str,
    payment_id: str,
    signature: str,
) -> None:
    """Check the checkout signature with the official SDK. Raises SignatureVerificationError."""
    client = razorpay.Client(auth=(key_id, key_secret))
    client.enable_retry(False)
    client.utility.verify_payment_signature(
        {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        }
    )


def verify_webhook_signature(*, body: bytes, signature: str, secret: str) -> None:
    """Check the webhook HMAC over the exact UTF-8 body. Raises SignatureVerificationError."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SignatureVerificationError("Webhook signature is invalid") from exc
    client = razorpay.Client(auth=("webhook", secret))
    client.enable_retry(False)
    client.utility.verify_webhook_signature(text, signature, secret)


def charge_currency(settings: Settings) -> str:
    currency = (settings.razorpay_currency or "").strip().upper()
    if currency != "INR":
        raise PaymentOrderError("Unsupported currency", status_code=422)
    return currency


class RazorpayOrderGateway:
    """Creates one Razorpay order. A lost response is reported as unknown."""

    def __init__(self, key_id: str, key_secret: str):
        self._client = razorpay.Client(auth=(key_id, key_secret))
        self._client.enable_retry(False)

    def create_order(
        self,
        *,
        amount_paise: int,
        currency: str,
        receipt: str,
        notes: dict[str, str],
    ) -> dict:
        try:
            payload = self._client.order.create(
                data={
                    "amount": amount_paise,
                    "currency": currency,
                    "receipt": receipt,
                    "notes": notes,
                }
            )
        except BadRequestError as exc:
            raise PaymentOrderError("Payment gateway rejected the order", status_code=502) from exc
        except (ServerError, GatewayError, requests.Timeout, requests.ConnectionError) as exc:
            raise PaymentOrderError(
                "Payment gateway did not confirm the order. It may already exist.",
                status_code=504,
                outcome_unknown=True,
            ) from exc
        except requests.RequestException as exc:
            raise PaymentOrderError(
                "Payment gateway did not confirm the order. It may already exist.",
                status_code=504,
                outcome_unknown=True,
            ) from exc
        if not isinstance(payload, dict):
            raise PaymentOrderError(
                "Payment gateway did not confirm the order. It may already exist.",
                status_code=504,
                outcome_unknown=True,
            )
        return payload


class RazorpayPaymentFetcher:
    """Reads one payment from Razorpay. Any gateway or network error returns None."""

    def __init__(self, key_id: str, key_secret: str):
        self._client = razorpay.Client(auth=(key_id, key_secret))
        self._client.enable_retry(False)

    def fetch_payment(self, payment_id: str) -> dict | None:
        try:
            payload = self._client.payment.fetch(payment_id)
        except (BadRequestError, ServerError, GatewayError, requests.RequestException):
            return None
        return payload if isinstance(payload, dict) else None
