"""API response schemas."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str


class RootResponse(BaseModel):
    """Root endpoint response."""

    message: str
