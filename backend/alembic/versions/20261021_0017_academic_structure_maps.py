"""Class-subject maps and teacher assignments for school academics.

Revision ID: 20261021_0017
Revises: 20261020_0016
Create Date: 2026-10-21

Additive only. Does not alter session_years, classes, sections, subjects,
class_sections, or staffs. Soft-delete friendly unique indexes apply only
while deleted_at IS NULL. Existing academic tables keep their original
integer reference columns without new foreign keys.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261021_0017"
down_revision: Union[str, None] = "20261020_0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "class_subjects",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_class_subjects_school_id", "class_subjects", ["school_id"])
    op.create_index("ix_class_subjects_class_id", "class_subjects", ["class_id"])
    op.create_index("ix_class_subjects_subject_id", "class_subjects", ["subject_id"])
    op.create_index(
        "uq_class_subjects_school_class_subject_active",
        "class_subjects",
        ["school_id", "class_id", "subject_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "teacher_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("teacher_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column(
            "class_section_id",
            sa.Integer(),
            sa.ForeignKey("class_sections.id"),
            nullable=True,
        ),
        sa.Column(
            "session_year_id",
            sa.Integer(),
            sa.ForeignKey("session_years.id"),
            nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_teacher_assignments_school_id", "teacher_assignments", ["school_id"])
    op.create_index("ix_teacher_assignments_staff_id", "teacher_assignments", ["staff_id"])
    op.create_index(
        "ix_teacher_assignments_teacher_user_id",
        "teacher_assignments",
        ["teacher_user_id"],
    )
    op.create_index("ix_teacher_assignments_subject_id", "teacher_assignments", ["subject_id"])
    op.create_index(
        "ix_teacher_assignments_class_section_id",
        "teacher_assignments",
        ["class_section_id"],
    )
    op.create_index(
        "ix_teacher_assignments_session_year_id",
        "teacher_assignments",
        ["session_year_id"],
    )
    # Partial unique including nullable columns. Duplicate prevention for NULL
    # class_section_id / session_year_id is also enforced in the service layer
    # because PostgreSQL treats NULLs as distinct in unique indexes.
    op.create_index(
        "uq_teacher_assignments_active",
        "teacher_assignments",
        ["school_id", "staff_id", "subject_id", "class_section_id", "session_year_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_teacher_assignments_active", table_name="teacher_assignments")
    op.drop_index("ix_teacher_assignments_session_year_id", table_name="teacher_assignments")
    op.drop_index("ix_teacher_assignments_class_section_id", table_name="teacher_assignments")
    op.drop_index("ix_teacher_assignments_subject_id", table_name="teacher_assignments")
    op.drop_index("ix_teacher_assignments_teacher_user_id", table_name="teacher_assignments")
    op.drop_index("ix_teacher_assignments_staff_id", table_name="teacher_assignments")
    op.drop_index("ix_teacher_assignments_school_id", table_name="teacher_assignments")
    op.drop_table("teacher_assignments")
    op.drop_index(
        "uq_class_subjects_school_class_subject_active",
        table_name="class_subjects",
    )
    op.drop_index("ix_class_subjects_subject_id", table_name="class_subjects")
    op.drop_index("ix_class_subjects_class_id", table_name="class_subjects")
    op.drop_index("ix_class_subjects_school_id", table_name="class_subjects")
    op.drop_table("class_subjects")
