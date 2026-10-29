"""Additive: timetable room + salary_components catalog.

Revision ID: 20261029_0042
Revises: 20261029_0041
Create Date: 2026-10-29

Do not apply to Neon from this delivery without explicit approval.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261029_0042"
down_revision: Union[str, None] = "20261029_0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "class_timetable_entries",
        sa.Column("room", sa.String(length=128), nullable=True),
    )

    op.create_table(
        "salary_components",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="earning"),
        sa.Column("calc_type", sa.String(length=16), nullable=False, server_default="fixed"),
        sa.Column("default_value", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_salary_components_school_id", "salary_components", ["school_id"])
    op.create_index(
        "ix_salary_components_school_kind",
        "salary_components",
        ["school_id", "kind"],
    )


def downgrade() -> None:
    op.drop_index("ix_salary_components_school_kind", table_name="salary_components")
    op.drop_index("ix_salary_components_school_id", table_name="salary_components")
    op.drop_table("salary_components")
    op.drop_column("class_timetable_entries", "room")
