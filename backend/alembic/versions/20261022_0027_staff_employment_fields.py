"""Add staff employment fields: employee_id, joining_date, employment_status.

Revision ID: 20261022_0027
Revises: 20261022_0026
Create Date: 2026-10-22

Additive only. Existing staff rows get employment_status='active' via server default.
employee_id and joining_date remain nullable for legacy rows.
Does not assign Spatie Teacher roles (new teachers get the role in application code).
Does not apply automatically — review and run alembic upgrade when approved.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0027"
down_revision: Union[str, None] = "20261022_0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "staffs",
        sa.Column("employee_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "staffs",
        sa.Column("joining_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "staffs",
        sa.Column(
            "employment_status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
    )
    op.create_index(
        "uq_staffs_school_employee_id",
        "staffs",
        ["school_id", "employee_id"],
        unique=True,
        postgresql_where=sa.text("employee_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_staffs_school_employee_id",
        table_name="staffs",
        postgresql_where=sa.text("employee_id IS NOT NULL"),
    )
    op.drop_column("staffs", "employment_status")
    op.drop_column("staffs", "joining_date")
    op.drop_column("staffs", "employee_id")
