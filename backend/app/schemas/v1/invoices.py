"""Issued subscription receipt. Amounts are integer paise. Tax fields are null when tax is not configured."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.v1.common import PaginatedResponse


class SubscriptionInvoiceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    invoice_number: str
    issued_at: datetime
    payment_transaction_id: int
    bill_id: int
    school_id: int
    subscription_id: int
    package_id: int
    gateway: str
    order_id: str
    payment_id: str
    currency: str
    amount: int
    tax_label: Optional[str] = None
    tax_rate_percent: Optional[str] = None
    tax_amount: Optional[int] = None
    total_amount: int
    school_name: str
    school_address: str
    school_email: str
    school_phone: str
    plan_name: str
    plan_description: Optional[str] = None
    cycle: str
    period_start: date
    period_end: date


class SubscriptionInvoiceListResponse(PaginatedResponse):
    items: list[SubscriptionInvoiceResponse]
