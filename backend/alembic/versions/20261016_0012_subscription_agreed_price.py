"""Nullable agreed price snapshot on subscriptions.

Revision ID: 20261016_0012
Revises: 20261015_0011
Create Date: 2026-10-16

Adds subscriptions.agreed_price only. Existing rows stay NULL. This revision
does not backfill from the current plan price, and it does not change
packages, subscription_bills, or subscription_renewals.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261016_0012"
down_revision: Union[str, None] = "20261015_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("agreed_price", sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "agreed_price")
