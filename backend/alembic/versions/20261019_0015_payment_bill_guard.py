"""One open payment per bill, and webhook diagnostics.

Revision ID: 20261019_0015
Revises: 20261017_0014
Create Date: 2026-10-19

Adds a partial unique index so a bill has at most one payment transaction
that is not refunded (status 4). That limits a bill to one payable order and
one captured payment. Adds nullable diagnostic columns to
payment_webhook_events. Does not change bills, subscriptions, or invoices.

Before upgrading a database that already has payment rows, check that no
bill has two non-refunded rows, or the index creation fails:

    SELECT bill_id, count(*) FROM payment_transactions
    WHERE status <> 4 GROUP BY bill_id HAVING count(*) > 1;
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_0015"
down_revision: Union[str, None] = "20261017_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_payment_transactions_bill_open",
        "payment_transactions",
        ["bill_id"],
        unique=True,
        postgresql_where=sa.text("status <> 4"),
    )
    op.add_column("payment_webhook_events", sa.Column("gateway_order_id", sa.String(length=64), nullable=True))
    op.add_column("payment_webhook_events", sa.Column("gateway_payment_id", sa.String(length=64), nullable=True))
    op.add_column("payment_webhook_events", sa.Column("amount_paise", sa.BigInteger(), nullable=True))
    op.add_column("payment_webhook_events", sa.Column("currency", sa.String(length=3), nullable=True))
    op.add_column("payment_webhook_events", sa.Column("outcome", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("payment_webhook_events", "outcome")
    op.drop_column("payment_webhook_events", "currency")
    op.drop_column("payment_webhook_events", "amount_paise")
    op.drop_column("payment_webhook_events", "gateway_payment_id")
    op.drop_column("payment_webhook_events", "gateway_order_id")
    op.drop_index("uq_payment_transactions_bill_open", table_name="payment_transactions")
