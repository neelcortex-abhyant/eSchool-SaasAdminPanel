from sqlalchemy.orm import DeclarativeBase


class V1Base(DeclarativeBase):
    """Separate metadata for /api/v1 Neon tables — never mix with legacy MySQL Base."""
