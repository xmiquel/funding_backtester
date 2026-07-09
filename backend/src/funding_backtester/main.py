"""Main FastAPI application for funding_backtester."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from funding_backtester.api.v1 import features, health, ohlcv
from funding_backtester.schemas.api import RootResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from funding_backtester.database import engine

    yield
    await engine.dispose()


app = FastAPI(
    title="funding_backtester",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router, tags=["health"])
app.include_router(features.router, tags=["features"])
app.include_router(ohlcv.router, tags=["ohlcv"])


@app.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    return RootResponse(message="funding_backtester API")
