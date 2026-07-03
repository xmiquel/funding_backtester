"""Async test fixtures."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from funding_backtester.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
