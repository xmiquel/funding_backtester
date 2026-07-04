"""OHLCV query endpoint."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from funding_backtester.config import settings
from funding_backtester.schemas.api import OHLCVBar
from funding_backtester.services.duckdb_client import DuckDBClient

router = APIRouter(prefix="/api/v1")

_GRANULARITY_MAP: dict[str, str] = {
    "15s": "ohlcv_15s",
    "1m": "ohlcv_1m",
    "3m": "ohlcv_3m",
    "5m": "ohlcv_5m",
    "15m": "ohlcv_15m",
    "1h": "ohlcv_1h",
    "3h": "ohlcv_3h",
    "4h": "ohlcv_4h",
    "1d": "ohlcv_1d",
}

_VALID_GRANULARITIES = set(_GRANULARITY_MAP)
_ALLOWED_TABLES = set(_GRANULARITY_MAP.values())

# Singleton DuckDB client — lazy initialized on first request
_client: DuckDBClient | None = None


def _get_duckdb() -> DuckDBClient:
    """Dependency: provide a shared DuckDB client instance."""
    global _client
    if _client is None:
        _client = DuckDBClient(settings.duckdb_path)
    return _client


def _build_query_sql(table_name: str) -> str:
    """Build parameterized query SQL for the given table.

    The table_name MUST come from _ALLOWED_TABLES (validated against
    the _GRANULARITY_MAP allow-list). This ensures only known table
    identifiers are interpolated into the SQL string.
    """
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Unexpected table name: {table_name}")
    return f"""  # nosec - table_name validated against _ALLOWED_TABLES allow-list
        SELECT datetime, symbol, open, high, low, close, volume,
               bid_open, bid_high, bid_low, bid_close,
               ask_open, ask_high, ask_low, ask_close
        FROM {table_name}
        WHERE symbol = ?
          AND datetime >= ?
          AND datetime < ?
        ORDER BY datetime ASC
    """


@router.get("/ohlcv", response_model=list[OHLCVBar])
async def get_ohlcv(
    symbol: str = Query(..., description="Futures contract symbol"),  # noqa: B008
    granularity: str = Query(  # noqa: B008
        "15s", description="OHLCV bar granularity (15s, 1m, 3m, 5m, 15m, 1h, 3h, 4h, 1d)"
    ),
    start_date: datetime.date | None = Query(  # noqa: B008
        None, description="Start date (inclusive)"
    ),
    end_date: datetime.date | None = Query(  # noqa: B008
        None, description="End date (exclusive)"
    ),
    duck: DuckDBClient = Depends(_get_duckdb),  # noqa: B008
) -> list[OHLCVBar]:
    """Return OHLCV bars for a symbol at the specified granularity.

    Supports: 15s, 1m, 3m, 5m, 15m, 1h, 3h, 4h, 1d.
    Results are sorted by datetime ascending.

    Raises HTTP 422 if granularity is not in the supported set.
    """
    if granularity not in _VALID_GRANULARITIES:
        valid = ", ".join(sorted(_VALID_GRANULARITIES))
        raise HTTPException(
            status_code=422,
            detail=[
                {
                    "type": "enum",
                    "loc": ("query", "granularity"),
                    "msg": f"Invalid granularity '{granularity}'. Must be one of: {valid}",
                    "input": granularity,
                }
            ],
        )

    table_name = _GRANULARITY_MAP[granularity]
    query_sql = _build_query_sql(table_name)

    start = start_date or datetime.date(1970, 1, 1)
    end = end_date or datetime.date(2099, 12, 31)
    # end_date is exclusive — convert to datetime for DuckDB query
    start_dt = datetime.datetime.combine(start, datetime.time.min)
    end_dt = datetime.datetime.combine(end, datetime.time.min)

    rows = await duck.query(
        query_sql,
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
