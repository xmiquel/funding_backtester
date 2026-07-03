"""Health check endpoint."""

from fastapi import APIRouter

from funding_backtester.schemas.api import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
