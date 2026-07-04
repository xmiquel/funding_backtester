"""OHLCV query endpoint."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query

from funding_backtester.config import settings
from funding_backtester.schemas.api import OHLCVBar
from funding_backtester.services.duckdb_client import DuckDBClient

router = APIRouter()

_QUERY_SQL = """
    SELECT datetime, symbol, open, high, low, close, volume,
           bid_open, bid_high, bid_low, bid_close,
           ask_open, ask_high, ask_low, ask_close
    FROM ohlcv_15s
    WHERE symbol = ?
      AND datetime >= ?
      AND datetime < ?
    ORDER BY datetime ASC
"""

# Singleton DuckDB client — lazy initialized on first request
_client: DuckDBClient | None = None


def _get_duckdb() -> DuckDBClient:
    """Dependency: provide a shared DuckDB client instance."""
    global _client
    if _client is None:
        _client = DuckDBClient(settings.duckdb_path)
    return _client


@router.get("/ohlcv", response_model=list[OHLCVBar])
async def get_ohlcv(
    symbol: str = Query(..., description="Futures contract symbol"),  # noqa: B008
    start_date: datetime.date | None = Query(  # noqa: B008
        None, description="Start date (inclusive)"
    ),
    end_date: datetime.date | None = Query(  # noqa: B008
        None, description="End date (exclusive)"
    ),
    duck: DuckDBClient = Depends(_get_duckdb),  # noqa: B008
) -> list[OHLCVBar]:
    """Return 15-second OHLCV bars for a symbol, optionally filtered by date.

    Results are sorted by datetime ascending.
    """
    start = start_date or datetime.date(1970, 1, 1)
    end = end_date or datetime.date(2099, 12, 31)
    # end_date is exclusive — convert to datetime for DuckDB query
    start_dt = datetime.datetime.combine(start, datetime.time.min)
    end_dt = datetime.datetime.combine(end, datetime.time.min)

    rows = await duck.query(
        _QUERY_SQL,
        [symbol, start_dt.isoformat(), end_dt.isoformat()],
    )

    # DuckDB returns correctly-typed values at runtime, but mypy can't
    # infer the tuple element types from the query() generic return.
    return [
        OHLCVBar(
            datetime=row[0],  # type: ignore[arg-type]
            symbol=row[1],  # type: ignore[arg-type]
            open=row[2],  # type: ignore[arg-type]
            high=row[3],  # type: ignore[arg-type]
            low=row[4],  # type: ignore[arg-type]
            close=row[5],  # type: ignore[arg-type]
            volume=row[6],  # type: ignore[arg-type]
            bid_open=row[7],  # type: ignore[arg-type]
            bid_high=row[8],  # type: ignore[arg-type]
            bid_low=row[9],  # type: ignore[arg-type]
            bid_close=row[10],  # type: ignore[arg-type]
            ask_open=row[11],  # type: ignore[arg-type]
            ask_high=row[12],  # type: ignore[arg-type]
            ask_low=row[13],  # type: ignore[arg-type]
            ask_close=row[14],  # type: ignore[arg-type]
        )
        for row in rows
    ]
