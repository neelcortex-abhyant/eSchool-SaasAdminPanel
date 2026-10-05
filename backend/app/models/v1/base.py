from sqlalchemy.orm import DeclarativeBase


class V1Base(DeclarativeBase):
    """Metadata for /api/v1 tables (v1_users, auth_sessions) on the shared Neon DB.

    Kept separate from legacy Base so Alembic can manage both without merging
    incompatible User models (UUID v1 vs integer Laravel users).
    """
