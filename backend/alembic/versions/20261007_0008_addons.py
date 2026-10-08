"""Phase 6: addons + addon_subscriptions tables.

Revision ID: 20261007_0008
Revises: 20261007_0007
Create Date: 2026-10-07

Additive only. No payment gateways or feature catalogs.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261007_0008"
down_revision: Union[str, None] = "20261007_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "addons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_addons_name", "addons", ["name"])
    op.create_index("ix_addons_status", "addons", ["status"])

    op.create_table(
        "addon_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("addon_id", sa.Integer(), sa.ForeignKey("addons.id"), nullable=False),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("subscriptions.id"),
            nullable=False,
        ),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_addon_subscriptions_school_id", "addon_subscriptions", ["school_id"])
    op.create_index("ix_addon_subscriptions_addon_id", "addon_subscriptions", ["addon_id"])
    op.create_index(
        "ix_addon_subscriptions_subscription_id", "addon_subscriptions", ["subscription_id"]
    )
    op.create_index("ix_addon_subscriptions_status", "addon_subscriptions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_addon_subscriptions_status", table_name="addon_subscriptions")
    op.drop_index("ix_addon_subscriptions_subscription_id", table_name="addon_subscriptions")
    op.drop_index("ix_addon_subscriptions_addon_id", table_name="addon_subscriptions")
    op.drop_index("ix_addon_subscriptions_school_id", table_name="addon_subscriptions")
    op.drop_table("addon_subscriptions")
    op.drop_index("ix_addons_status", table_name="addons")
    op.drop_index("ix_addons_name", table_name="addons")
    op.drop_table("addons")
