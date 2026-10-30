"""Four modules: salary assignment history, payroll unpaid-leave flag.

Revision ID: 20261030_0044
Revises: 20261029_0043
Create Date: 2026-10-30

Do not apply to Neon without explicit approval.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_0044"
down_revision: Union[str, None] = "20261029_0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("salary_assignments", sa.Column("effective_to", sa.Date(), nullable=True))
    op.drop_index("uq_salary_assignments_staff_active", table_name="salary_assignments")
    op.create_index(
        "uq_salary_assignments_staff_current",
        "salary_assignments",
        ["school_id", "staff_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND effective_to IS NULL"),
    )

    op.add_column(
        "payroll_settings",
        sa.Column(
            "apply_unpaid_leave_adjustment",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "payroll_settings",
        sa.Column(
            "working_days_per_month",
            sa.Integer(),
            nullable=True,
        ),
    )

    # Keep one authoritative run per period across processed + paid.
    op.drop_index("uq_payroll_runs_school_period_active", table_name="payroll_runs")
    op.create_index(
        "uq_payroll_runs_school_period_final",
        "payroll_runs",
        ["school_id", "period_label"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND status IN ('processed', 'paid')"
        ),
    )

    op.add_column(
        "conversation_messages",
        sa.Column("attachments_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversation_messages", "attachments_json")
    op.drop_index("uq_payroll_runs_school_period_final", table_name="payroll_runs")
    op.create_index(
        "uq_payroll_runs_school_period_active",
        "payroll_runs",
        ["school_id", "period_label"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'processed'"),
    )
    op.drop_column("payroll_settings", "working_days_per_month")
    op.drop_column("payroll_settings", "apply_unpaid_leave_adjustment")
    op.drop_index("uq_salary_assignments_staff_current", table_name="salary_assignments")
    op.create_index(
        "uq_salary_assignments_staff_active",
        "salary_assignments",
        ["school_id", "staff_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_column("salary_assignments", "effective_to")
