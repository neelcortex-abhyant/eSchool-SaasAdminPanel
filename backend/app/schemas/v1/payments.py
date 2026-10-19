"""Payment initiation request and response. Amount is integer paise."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.v1.common import PaginatedResponse


class PaymentInitiateRequest(BaseModel):
    """Client amount is not a field. Extra fields, including amount, are rejected."""

    model_config = ConfigDict(extra="forbid")

    bill_id: int = Field(ge=1)
    school_id: int = Field(ge=1)
    subscription_id: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=64)


class PaymentVerifyRequest(BaseModel):
    """The signature is checked with the key secret. A client amount is rejected."""

    model_config = ConfigDict(extra="forbid")

    razorpay_order_id: str = Field(min_length=1, max_length=64)
    razorpay_payment_id: str = Field(min_length=1, max_length=64)
    razorpay_signature: str = Field(min_length=1, max_length=256)


class PaymentVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    payment_id: str
    amount: int
    currency: str
    status: str


class WebhookReceiptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    received: bool


class PaymentInitiateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    amount: int
    currency: str
    gateway: str
    key_id: str
    status: str


class PaymentTransactionResponse(BaseModel):
    """Safe payment fields. Amount is integer paise. No signatures or secrets."""

    model_config = ConfigDict(extra="forbid")

    id: int
    school_id: int
    bill_id: int
    gateway: str
    order_id: str
    payment_id: Optional[str] = None
    amount: int
    currency: str
    status: str
    invoice_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaymentTransactionListResponse(PaginatedResponse):
    items: list[PaymentTransactionResponse]


class PaymentSummaryResponse(BaseModel):
    """Aggregates over payment_transactions in one currency.

    successful = captured, pending = created or authorized, failed = failed.
    successful_amount_paise is the exact integer total. successful_amount is
    the same total in major units (rupees) for display.
    """

    model_config = ConfigDict(extra="forbid")

    currency: str
    successful_amount_paise: int
    successful_amount: float
    successful_count: int
    pending_count: int
    failed_count: int
    refunded_count: int
    total_count: int
