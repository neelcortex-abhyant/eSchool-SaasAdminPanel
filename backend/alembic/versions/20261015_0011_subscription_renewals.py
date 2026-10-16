"""Immutable subscription renewal snapshots.

Revision ID: 20261015_0011
Revises: 20261009_0010
Create Date: 2026-10-15

Adds subscription_renewals only. Does not change packages, subscriptions,
schools, or subscription_bills. Does not backfill older subscriptions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_0011"
down_revision: Union[str, None] = "20261009_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_renewals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id"),
            nullable=False,
        ),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("plan_name", sa.String(length=255), nullable=False),
        sa.Column("cycle", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "subscription_id",
            "period_start",
            name="uq_subscription_renewals_period",
        ),
    )
    op.create_index(
        "ix_subscription_renewals_subscription_id",
        "subscription_renewals",
        ["subscription_id"],
    )
    op.create_index(
        "ix_subscription_renewals_school_id",
        "subscription_renewals",
        ["school_id"],
    )
    op.create_index(
        "ix_subscription_renewals_package_id",
        "subscription_renewals",
        ["package_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_renewals_package_id", table_name="subscription_renewals")
    op.drop_index("ix_subscription_renewals_school_id", table_name="subscription_renewals")
    op.drop_index("ix_subscription_renewals_subscription_id", table_name="subscription_renewals")
    op.drop_table("subscription_renewals")
