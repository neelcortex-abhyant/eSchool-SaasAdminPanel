"""Study materials for class-section/subject (Module 4).

Revision ID: 20261023_0034
Revises: 20261023_0033
Create Date: 2026-10-23

Additive only. Soft-delete friendly. Does not apply automatically.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261023_0034"
down_revision: Union[str, None] = "20261023_0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "study_materials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column(
            "session_year_id",
            sa.Integer(),
            sa.ForeignKey("session_years.id"),
            nullable=False,
        ),
        sa.Column(
            "class_section_id",
            sa.Integer(),
            sa.ForeignKey("class_sections.id"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("teacher_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("staff_id", sa.Integer(), sa.ForeignKey("staffs.id"), nullable=False),
        sa.Column("uploaded_by_v1_user_id", sa.String(length=36), nullable=True),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("chapter", sa.String(length=255), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("external_url", sa.String(length=2048), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "resource_type IN ('file', 'video_link', 'document_reference')",
            name="ck_study_materials_resource_type",
        ),
        sa.CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="ck_study_materials_size_bytes",
        ),
    )
    op.create_index("ix_study_materials_school_id", "study_materials", ["school_id"])
    op.create_index("ix_study_materials_session_year_id", "study_materials", ["session_year_id"])
    op.create_index("ix_study_materials_class_section_id", "study_materials", ["class_section_id"])
    op.create_index("ix_study_materials_subject_id", "study_materials", ["subject_id"])
    op.create_index("ix_study_materials_teacher_user_id", "study_materials", ["teacher_user_id"])
    op.create_index("ix_study_materials_staff_id", "study_materials", ["staff_id"])
    op.create_index(
        "ix_study_materials_uploaded_by_v1_user_id",
        "study_materials",
        ["uploaded_by_v1_user_id"],
    )
    op.create_index(
        "ix_study_materials_school_session_cs",
        "study_materials",
        ["school_id", "session_year_id", "class_section_id"],
    )
    op.create_index(
        "ix_study_materials_school_subject",
        "study_materials",
        ["school_id", "subject_id"],
    )
    op.create_index(
        "ix_study_materials_school_teacher",
        "study_materials",
        ["school_id", "teacher_user_id"],
    )
    op.create_index(
        "ix_study_materials_resource_type",
        "study_materials",
        ["school_id", "resource_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_study_materials_resource_type", table_name="study_materials")
    op.drop_index("ix_study_materials_school_teacher", table_name="study_materials")
    op.drop_index("ix_study_materials_school_subject", table_name="study_materials")
    op.drop_index("ix_study_materials_school_session_cs", table_name="study_materials")
    op.drop_index("ix_study_materials_uploaded_by_v1_user_id", table_name="study_materials")
    op.drop_index("ix_study_materials_staff_id", table_name="study_materials")
    op.drop_index("ix_study_materials_teacher_user_id", table_name="study_materials")
    op.drop_index("ix_study_materials_subject_id", table_name="study_materials")
    op.drop_index("ix_study_materials_class_section_id", table_name="study_materials")
    op.drop_index("ix_study_materials_session_year_id", table_name="study_materials")
    op.drop_index("ix_study_materials_school_id", table_name="study_materials")
    op.drop_table("study_materials")
