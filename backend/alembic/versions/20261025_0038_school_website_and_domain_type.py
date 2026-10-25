"""Schools: school_website, domain_type, domain_verified + domain uniqueness.

Revision ID: 20261025_0038
Revises: 20261024_0037
Create Date: 2026-10-25

Additive only. Does not apply automatically.
``schools.domain`` continues to store the full application hostname.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261025_0038"
down_revision: Union[str, None] = "20261024_0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schools",
        sa.Column("school_website", sa.String(length=512), nullable=False, server_default=""),
    )
    op.add_column(
        "schools",
        sa.Column("domain_type", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "schools",
        sa.Column("domain_verified", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ix_schools_domain_nonblank
        ON schools (lower(btrim(domain)))
        WHERE domain IS NOT NULL AND btrim(domain) <> ''
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_schools_domain_nonblank")
    op.drop_column("schools", "domain_verified")
    op.drop_column("schools", "domain_type")
    op.drop_column("schools", "school_website")
