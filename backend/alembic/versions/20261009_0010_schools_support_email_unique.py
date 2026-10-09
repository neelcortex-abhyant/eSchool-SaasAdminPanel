"""Non-blank school support emails are unique case-insensitively.

Revision ID: 20261009_0010
Revises: 20261007_0009
Create Date: 2026-10-09

Blank support_email values stay allowed (column default ''). Existing rows are
not rewritten. The partial unique index excludes blank emails.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261009_0010"
down_revision: Union[str, None] = "20261007_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX ix_schools_support_email_nonblank
        ON schools (lower(btrim(support_email)))
        WHERE btrim(support_email) <> ''
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_schools_support_email_nonblank")
