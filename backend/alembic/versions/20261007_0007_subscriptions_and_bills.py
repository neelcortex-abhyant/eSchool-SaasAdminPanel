"""Phase 5: subscriptions + subscription_bills tables.

Revision ID: 20261007_0007
Revises: 20261007_0006
Create Date: 2026-10-07

Additive only. Does not implement addons, features, or payment gateways.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0007"
down_revision: Union[str, None] = "20261007_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("package_id", sa.Integer(), sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("cycle", sa.String(length=16), nullable=False, server_default="monthly"),
        sa.Column("auto_renew", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_subscriptions_school_id", "subscriptions", ["school_id"])
    op.create_index("ix_subscriptions_package_id", "subscriptions", ["package_id"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])

    op.create_table(
        "subscription_bills",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id"),
            nullable=False,
        ),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_subscription_bills_subscription_id", "subscription_bills", ["subscription_id"])
    op.create_index("ix_subscription_bills_school_id", "subscription_bills", ["school_id"])
    op.create_index("ix_subscription_bills_status", "subscription_bills", ["status"])


def downgrade() -> None:
    op.drop_index("ix_subscription_bills_status", table_name="subscription_bills")
    op.drop_index("ix_subscription_bills_school_id", table_name="subscription_bills")
    op.drop_index("ix_subscription_bills_subscription_id", table_name="subscription_bills")
    op.drop_table("subscription_bills")
    op.drop_index("ix_subscriptions_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_package_id", table_name="subscriptions")
    op.drop_index("ix_subscriptions_school_id", table_name="subscriptions")
    op.drop_table("subscriptions")
