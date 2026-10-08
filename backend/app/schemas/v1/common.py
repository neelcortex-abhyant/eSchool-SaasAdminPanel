from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str


class PaginatedResponse(BaseModel):
    """Shared v1 list envelope (no prior v1 pagination convention existed)."""

    items: list
    total: int
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
