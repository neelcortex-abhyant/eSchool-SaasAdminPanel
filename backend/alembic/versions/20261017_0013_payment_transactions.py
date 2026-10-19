"""Subscription payment transactions and processed webhook events.

Revision ID: 20261017_0013
Revises: 6bfcc3198722
Create Date: 2026-10-17

Adds payment_transactions and payment_webhook_events only. Does not change
packages, subscriptions, subscription_bills, or subscription_renewals.
Amounts are integer paise. Gateway secrets are not columns.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0013"
down_revision: Union[str, None] = "6bfcc3198722"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("subscription_bills.id"), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("gateway_order_id", sa.String(length=64), nullable=False),
        sa.Column("gateway_payment_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=True),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("gateway_order_id", name="uq_payment_transactions_gateway_order_id"),
        sa.UniqueConstraint("gateway_payment_id", name="uq_payment_transactions_gateway_payment_id"),
        sa.UniqueConstraint(
            "school_id",
            "idempotency_key",
            name="uq_payment_transactions_school_idempotency",
        ),
        sa.CheckConstraint(
            "amount_paise >= 0",
            name="ck_payment_transactions_amount_paise_non_negative",
        ),
    )
    op.create_index("ix_payment_transactions_bill_id", "payment_transactions", ["bill_id"])
    op.create_index("ix_payment_transactions_school_id", "payment_transactions", ["school_id"])
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"])
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="razorpay"),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column(
            "payment_transaction_id",
            sa.Integer(),
            sa.ForeignKey("payment_transactions.id"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "provider",
            "event_id",
            name="uq_payment_webhook_events_provider_event",
        ),
    )
    op.create_index(
        "ix_payment_webhook_events_payment_transaction_id",
        "payment_webhook_events",
        ["payment_transaction_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_payment_webhook_events_payment_transaction_id",
        table_name="payment_webhook_events",
    )
    op.drop_table("payment_webhook_events")
    op.drop_index("ix_payment_transactions_status", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_school_id", table_name="payment_transactions")
    op.drop_index("ix_payment_transactions_bill_id", table_name="payment_transactions")
    op.drop_table("payment_transactions")
