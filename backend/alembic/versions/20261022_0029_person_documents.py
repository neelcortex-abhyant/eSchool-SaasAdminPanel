"""Add person_documents metadata table for private teacher/staff files.

Revision ID: 20261022_0029
Revises: 20261022_0028
Create Date: 2026-10-22

Additive only. Stores metadata and opaque storage keys — not file bytes.
Does not configure object storage. Does not apply automatically.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0029"
down_revision: Union[str, None] = "20261022_0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "person_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("school_id", sa.Integer(), sa.ForeignKey("schools.id"), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_person_documents_school_id", "person_documents", ["school_id"])
    op.create_index(
        "ix_person_documents_owner_user_id",
        "person_documents",
        ["owner_user_id"],
    )
    op.create_index("ix_person_documents_category", "person_documents", ["category"])


def downgrade() -> None:
    op.drop_index("ix_person_documents_category", table_name="person_documents")
    op.drop_index("ix_person_documents_owner_user_id", table_name="person_documents")
    op.drop_index("ix_person_documents_school_id", table_name="person_documents")
    op.drop_table("person_documents")
