"""Feature discovery API endpoints.

Exposes the bounded indicator catalog and persisted feature data without
requiring consumers to import indicator internals.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, Query

from funding_backtester.config import settings
from funding_backtester.indicators.parameters import INDICATOR_CATALOG
from funding_backtester.schemas.api import (
    FeatureCatalogEntry,
    FeatureMetaResponse,
    FeatureRow,
)
from funding_backtester.services.duckdb_client import DuckDBClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

_FEATURE_TABLES = ("indicator_features", "indicator_feature_stage")


async def _get_db() -> AsyncGenerator[DuckDBClient | None]:
    """Dependency: provide a DuckDB client when database exists."""
    if not os.path.isfile(settings.duckdb_path):
        yield None
        return
    try:
        db = await asyncio.to_thread(DuckDBClient, settings.duckdb_path)
    except Exception:
        logger.exception("Failed to open DuckDB database at %s", settings.duckdb_path)
        yield None
        return
    try:
        yield db
    finally:
        db.close()


async def _resolve_feature_table(db: DuckDBClient) -> str | None:
    """Return the name of the first available feature table, or None."""
    for table in _FEATURE_TABLES:
        rows = await db.query(
            "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
            [table],
        )
        if rows:
            return table
    return None


def _build_feature_query(
    table: str,
    symbol: str,
    timeframe: str | None,
    feature_names: list[str] | None,
) -> tuple[str, list[object]]:
    """Build SQL query and params for feature retrieval."""
    if timeframe is not None and feature_names is not None and len(feature_names) > 0:
        placeholders = ", ".join("?" for _ in feature_names)
        sql = f"""
            SELECT datetime, symbol, timeframe, source_model,
                   feature_name, feature_id, parameter_hash, parameter_json,
                   output_name, value, computed_at, computation_version,
                   pandas_ta_classic_version, talib_available, talib_version, talib_used
            FROM {table}
            WHERE symbol = ? AND timeframe = ? AND feature_name IN ({placeholders})
            ORDER BY datetime ASC
        """  # nosec B608 — table resolved from internal _FEATURE_TABLES constant
        return sql, [symbol, timeframe, *feature_names]
    if timeframe is not None:
        sql = f"""
            SELECT datetime, symbol, timeframe, source_model,
                   feature_name, feature_id, parameter_hash, parameter_json,
                   output_name, value, computed_at, computation_version,
                   pandas_ta_classic_version, talib_available, talib_version, talib_used
            FROM {table}
            WHERE symbol = ? AND timeframe = ?
            ORDER BY datetime ASC
        """  # nosec B608 — table resolved from internal _FEATURE_TABLES constant
        return sql, [symbol, timeframe]
    if feature_names is not None and len(feature_names) > 0:
        placeholders = ", ".join("?" for _ in feature_names)
        params: list[object] = [symbol, *feature_names]
        sql = f"""
            SELECT datetime, symbol, timeframe, source_model,
                   feature_name, feature_id, parameter_hash, parameter_json,
                   output_name, value, computed_at, computation_version,
                   pandas_ta_classic_version, talib_available, talib_version, talib_used
            FROM {table}
            WHERE symbol = ? AND feature_name IN ({placeholders})
            ORDER BY datetime ASC
        """  # nosec B608 — table resolved from internal _FEATURE_TABLES constant
        return sql, params

    sql = f"""
        SELECT datetime, symbol, timeframe, source_model,
               feature_name, feature_id, parameter_hash, parameter_json,
               output_name, value, computed_at, computation_version,
               pandas_ta_classic_version, talib_available, talib_version, talib_used
        FROM {table}
        WHERE symbol = ?
        ORDER BY datetime ASC
    """  # nosec B608 — table resolved from internal _FEATURE_TABLES constant
    return sql, [symbol]


def _row_to_feature(row: tuple[object, ...]) -> FeatureRow:
    """Convert a DuckDB result row to a FeatureRow."""
    return FeatureRow(
        datetime=row[0],
        symbol=row[1],
        timeframe=row[2],
        source_model=row[3],
        feature_name=row[4],
        feature_id=row[5],
        parameter_hash=row[6],
        parameter_json=row[7],
        output_name=row[8],
        value=row[9],
        computed_at=row[10],
        computation_version=row[11],
        pandas_ta_classic_version=str(row[12]),
        talib_available=bool(row[13]),
        talib_version=str(row[14]) if row[14] else None,
        talib_used=bool(row[15]),
    )


async def _execute_feature_query(
    db: DuckDBClient,
    table: str,
    symbol: str,
    timeframe: str | None,
    feature_names: list[str] | None,
) -> list[FeatureRow]:
    """Execute a feature query asynchronously and return typed rows."""
    sql, params = _build_feature_query(table, symbol, timeframe, feature_names)
    rows = await db.query(sql, params)
    return [_row_to_feature(row) for row in rows]


@router.get("/features/catalog", response_model=list[FeatureCatalogEntry])
async def get_feature_catalog() -> list[FeatureCatalogEntry]:
    """Return the bounded indicator catalog.

    Static data from the parameters module — no database dependency.
    """
    return [
        FeatureCatalogEntry(
            name=definition.name,
            library=definition.library,
            parameters=dict(definition.parameters),
            outputs=list(definition.outputs),
            min_lookback=definition.min_lookback,
        )
        for definition in INDICATOR_CATALOG.values()
    ]


@router.get("/features/meta", response_model=FeatureMetaResponse)
async def get_feature_meta(
    db: DuckDBClient | None = Depends(_get_db),  # noqa: B008
) -> FeatureMetaResponse:
    """Return available symbols, timeframes, and source models."""
    if db is None:
        return FeatureMetaResponse(symbols=[], timeframes=[], source_models=[])

    try:
        table = await _resolve_feature_table(db)
        if table is None:
            return FeatureMetaResponse(symbols=[], timeframes=[], source_models=[])

        rows = await db.query(
            f"SELECT DISTINCT symbol, timeframe, source_model FROM {table}"  # nosec B608
        )
    except Exception:
        logger.exception("Failed to load feature metadata from DuckDB")
        return FeatureMetaResponse(symbols=[], timeframes=[], source_models=[])

    symbols: set[str] = set()
    timeframes: set[str] = set()
    source_models: set[str] = set()
    for row in rows:
        symbols.add(str(row[0]))
        timeframes.add(str(row[1]))
        source_models.add(str(row[2]))
    return FeatureMetaResponse(
        symbols=sorted(symbols),
        timeframes=sorted(timeframes),
        source_models=sorted(source_models),
    )


@router.get("/features", response_model=list[FeatureRow])
async def get_features(
    db: DuckDBClient | None = Depends(_get_db),  # noqa: B008
    symbol: str = Query(..., description="Futures contract symbol"),  # noqa: B008
    timeframe: str | None = Query(  # noqa: B008
        None, description="OHLCV time bucket (e.g. 15s, 1m)"
    ),
    feature_name: list[str] | None = Query(  # noqa: B008
        None, description="One or more feature names to filter"
    ),
) -> list[FeatureRow]:
    """Return persisted indicator feature rows.

    Required ``symbol`` filter with optional ``timeframe`` and
    ``feature_name`` filters.
    """
    if db is None:
        return []

    try:
        table = await _resolve_feature_table(db)
        if table is None:
            return []

        return await _execute_feature_query(db, table, symbol, timeframe, feature_name)
    except Exception:
        logger.exception("Failed to load feature rows from DuckDB")
        return []
