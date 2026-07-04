"""Async test fixtures."""

from __future__ import annotations

import pathlib

import duckdb
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from funding_backtester.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def memory_db():
    """In-memory DuckDB connection for SQL transformation testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# OHLCV test DuckDB — creates a temp database with ohlcv_15s data for
# API endpoint integration tests.
# ---------------------------------------------------------------------------


@pytest.fixture
def ohlcv_db_path(tmp_path: pathlib.Path) -> str:
    """Create a temporary DuckDB file with sample ohlcv_15s data.

    Returns the path to the DuckDB file for use in API tests.
    """
    db_path = str(tmp_path / "test_ohlcv.duckdb")
    conn = duckdb.connect(db_path)

    conn.execute("""
        CREATE TABLE ohlcv_15s (
            datetime TIMESTAMP,
            symbol VARCHAR,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT,
            bid_open DOUBLE,
            bid_high DOUBLE,
            bid_low DOUBLE,
            bid_close DOUBLE,
            ask_open DOUBLE,
            ask_high DOUBLE,
            ask_low DOUBLE,
            ask_close DOUBLE
        )
    """)

    # Insert test data: 3 bars for MNQ0626 and 2 for ESU0626
    conn.execute("""
        INSERT INTO ohlcv_15s VALUES
            ('2026-03-15 09:30:00', 'MNQ0626', 4500.25, 4500.75, 4500.00, 4500.50, 100,
             4500.20, 4500.70, 4499.95, 4500.45, 4500.30, 4500.80, 4500.05, 4500.55),
            ('2026-03-15 09:30:15', 'MNQ0626', 4500.50, 4501.00, 4500.25, 4500.80, 150,
             4500.45, 4500.95, 4500.20, 4500.75, 4500.55, 4501.05, 4500.30, 4500.85),
            ('2026-03-15 09:30:30', 'MNQ0626', 4500.80, 4501.25, 4500.60, 4501.00, 200,
             4500.75, 4501.20, 4500.55, 4500.95, 4500.85, 4501.30, 4500.65, 4501.05),
            ('2026-03-15 09:30:00', 'ESU0626', 5000.00, 5001.50, 4999.50, 5001.00, 80,
             4999.90, 5001.40, 4999.40, 5000.90, 5000.10, 5001.60, 4999.60, 5001.10),
            ('2026-03-15 09:30:15', 'ESU0626', 5001.00, 5002.00, 5000.50, 5001.75, 120,
             5000.90, 5001.90, 5000.40, 5001.65, 5001.10, 5002.10, 5000.60, 5001.85)
    """)
    conn.close()
    return db_path


@pytest.fixture
def ohlcv_client(ohlcv_db_path: str, monkeypatch: pytest.MonkeyPatch):
    """FastAPI client with duckdb_path overridden to a temp DB with test data."""
    monkeypatch.setattr("funding_backtester.config.settings.duckdb_path", ohlcv_db_path)
    # Clear the singleton DuckDB client so the next request opens the test DB
    import funding_backtester.api.v1.ohlcv as ohlcv_mod

    ohlcv_mod._client = None

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")
    return client
