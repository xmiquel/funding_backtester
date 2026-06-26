"""Main FastAPI application for funding_backtester."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from funding_backtester.config import settings
from funding_backtester.api.v1 import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    from funding_backtester.database import engine
    yield
    await engine.dispose()


app = FastAPI(
    title="funding_backtester",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])


@app.get("/")
async def root():
    return {"message": "funding_backtester API"}