"""Subscription invoice snapshots and yearly invoice numbers.

Revision ID: 20261017_0014
Revises: 20261017_0013
Create Date: 2026-10-17

Adds subscription_invoices and subscription_invoice_counters only.
Does not change packages, subscriptions, subscription_bills,
subscription_renewals, or payment_transactions.
Tax columns are nullable because no tax configuration exists.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0014"
down_revision: Union[str, None] = "20261017_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_invoice_counters",
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False),
    )
    op.create_table(
        "subscription_invoices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("invoice_number", sa.String(length=32), nullable=False),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
        sa.Column(
            "payment_transaction_id",
            sa.Integer(),
            sa.ForeignKey("payment_transactions.id"),
            nullable=False,
        ),
        sa.Column("bill_id", sa.Integer(), sa.ForeignKey("subscription_bills.id"), nullable=False),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), sa.ForeignKey("subscriptions.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("gateway", sa.String(length=32), nullable=False),
        sa.Column("gateway_order_id", sa.String(length=64), nullable=False),
        sa.Column("gateway_payment_id", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("tax_label", sa.String(length=32), nullable=True),
        sa.Column("tax_rate_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("tax_amount_paise", sa.BigInteger(), nullable=True),
        sa.Column("total_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("school_name", sa.String(length=255), nullable=False),
        sa.Column("school_address", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("school_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("school_phone", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("plan_name", sa.String(length=255), nullable=False),
        sa.Column("plan_description", sa.String(length=255), nullable=True),
        sa.Column("cycle", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.UniqueConstraint("invoice_number", name="uq_subscription_invoices_number"),
        sa.UniqueConstraint("payment_transaction_id", name="uq_subscription_invoices_payment"),
        sa.CheckConstraint("amount_paise >= 0", name="ck_subscription_invoices_amount_non_negative"),
        sa.CheckConstraint(
            "total_amount_paise >= 0",
            name="ck_subscription_invoices_total_non_negative",
        ),
    )
    op.create_index("ix_subscription_invoices_bill_id", "subscription_invoices", ["bill_id"])
    op.create_index("ix_subscription_invoices_school_id", "subscription_invoices", ["school_id"])
    op.create_index(
        "ix_subscription_invoices_subscription_id",
        "subscription_invoices",
        ["subscription_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_invoices_subscription_id", table_name="subscription_invoices")
    op.drop_index("ix_subscription_invoices_school_id", table_name="subscription_invoices")
    op.drop_index("ix_subscription_invoices_bill_id", table_name="subscription_invoices")
    op.drop_table("subscription_invoices")
    op.drop_table("subscription_invoice_counters")
