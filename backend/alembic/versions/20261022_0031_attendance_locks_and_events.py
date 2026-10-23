"""Attendance locks and absence/leave event outbox.

Revision ID: 20261022_0031
Revises: 20261022_0030
Create Date: 2026-10-22

Additive only. Does not rewrite attendance identity or apply automatically.

Tables:
- attendance_locks: persistent date / class-section locks
- attendance_events: outbox for future absence/leave notifications (no delivery)

Correction history uses existing audit_logs (action=attendance.correct).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0031"
down_revision: Union[str, None] = "20261022_0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attendance_locks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("session_year_id", sa.Integer(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("class_section_id", sa.Integer(), nullable=True),
        sa.Column("locked_by", sa.String(length=36), nullable=True),
        sa.Column(
            "reason",
            sa.String(length=512),
            server_default="",
            nullable=False,
        ),
        sa.Column("unlocked_at", sa.DateTime(), nullable=True),
        sa.Column("unlocked_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_attendance_locks_school_id",
        "attendance_locks",
        ["school_id"],
    )
    op.create_index(
        "ix_attendance_locks_session_year_id",
        "attendance_locks",
        ["session_year_id"],
    )
    op.create_index(
        "ix_attendance_locks_class_section_id",
        "attendance_locks",
        ["class_section_id"],
    )
    op.create_index(
        "ix_attendance_locks_school_date",
        "attendance_locks",
        ["school_id", "attendance_date"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_attendance_locks_active
        ON attendance_locks (
            school_id,
            session_year_id,
            attendance_date,
            COALESCE(class_section_id, 0)
        )
        WHERE unlocked_at IS NULL
        """
    )
    op.create_table(
        "attendance_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("attendance_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("session_year_id", sa.Integer(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("status_type", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_attendance_events_school_id",
        "attendance_events",
        ["school_id"],
    )
    op.create_index(
        "ix_attendance_events_attendance_id",
        "attendance_events",
        ["attendance_id"],
    )
    op.create_index(
        "ix_attendance_events_student_id",
        "attendance_events",
        ["student_id"],
    )
    op.create_index(
        "ix_attendance_events_unprocessed",
        "attendance_events",
        ["processed_at", "event_type"],
    )
    op.create_index(
        "ix_attendance_events_school_created",
        "attendance_events",
        ["school_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_attendance_events_school_created", table_name="attendance_events")
    op.drop_index("ix_attendance_events_unprocessed", table_name="attendance_events")
    op.drop_index("ix_attendance_events_student_id", table_name="attendance_events")
    op.drop_index("ix_attendance_events_attendance_id", table_name="attendance_events")
    op.drop_index("ix_attendance_events_school_id", table_name="attendance_events")
    op.drop_table("attendance_events")
    op.execute("DROP INDEX IF EXISTS uq_attendance_locks_active")
    op.drop_index("ix_attendance_locks_school_date", table_name="attendance_locks")
    op.drop_index("ix_attendance_locks_class_section_id", table_name="attendance_locks")
    op.drop_index("ix_attendance_locks_session_year_id", table_name="attendance_locks")
    op.drop_index("ix_attendance_locks_school_id", table_name="attendance_locks")
    op.drop_table("attendance_locks")
