"""Borde de persistencia en DuckDB para features de indicadores.

Este módulo actúa como boundary/repository explícito para el storage analítico
de features en DuckDB. No usa la base transaccional del backend
(`SQLAlchemy`/`asyncpg`) ni participa del request path de FastAPI: su ejecución
es síncrona por diseño porque se consume desde CLI, jobs offline y la capa de
persistencia/poblado de features.

El SQL raw queda encapsulado aquí porque el acceso es controlado y acotado a
DuckDB. Los identificadores de tabla/modelo se validan antes de interpolarse y
los valores externos se pasan por parámetros, manteniendo el límite de
seguridad en este boundary.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import duckdb

from funding_backtester.indicators.engine import compute_indicator_series
from funding_backtester.indicators.parameters import (
    canonical_parameter_json,
    feature_id,
    parameter_hash,
)
from funding_backtester.indicators.registry import validate_indicator_request

COMPUTATION_VERSION = "indicator-layer-v1"
_SOURCE_MODEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

STAGE_COLUMNS = (
    "datetime",
    "symbol",
    "timeframe",
    "source_model",
    "feature_name",
    "feature_id",
    "parameter_hash",
    "parameter_json",
    "output_name",
    "value",
    "computed_at",
    "computation_version",
    "pandas_ta_classic_version",
    "talib_available",
    "talib_version",
    "talib_used",
)


def build_indicator_feature_stage(
    database_path: str | Path,
    *,
    source_model: str,
    timeframe: str,
    feature_names: Iterable[str],
) -> int:
    """Calcula features de indicadores desde DuckDB hacia la tabla de stage.

    Esta función pertenece al boundary de persistencia analítica de DuckDB, no
    a la capa transaccional del backend. La ejecución es síncrona porque se usa
    en flujos offline/CLI y no en handlers HTTP.
    """
    _validate_source_model(source_model)
    requests = [validate_indicator_request(feature_name) for feature_name in feature_names]
    conn = duckdb.connect(str(database_path))
    try:
        frame = conn.execute(
            f"""
            SELECT datetime, symbol, open, high, low, close, volume
            FROM {source_model}
            ORDER BY symbol, datetime
            """  # nosec B608 — source_model validado por la expresión regular de _validate_source_model
        ).df()
        if frame.empty:
            msg = (
                f"No rows found in source_model {source_model!r}; refusing to replace "
                "indicator_feature_stage"
            )
            raise RuntimeError(msg)

        _ensure_stage_table(conn)
        computed_at = _stable_computed_at(frame)
        rows: list[tuple[object, ...]] = []
        for symbol, symbol_frame in frame.groupby("symbol", sort=True):
            ordered_frame = symbol_frame.sort_values("datetime").reset_index(drop=True)
            for request in requests:
                result = compute_indicator_series(
                    request.name,
                    ordered_frame,
                    parameters=request.parameters,
                )
                feature_rows = _stage_rows(
                    result_frame=result.frame,
                    metadata=result.metadata,
                    symbol=str(symbol),
                    timeframe=timeframe,
                    source_model=source_model,
                    feature_name=request.name,
                    output_names=request.outputs,
                    parameters=request.parameters,
                    computed_at=computed_at,
                )
                rows.extend(feature_rows)
        _replace_stage_rows(
            conn,
            rows,
            source_model=source_model,
            timeframe=timeframe,
            feature_names=tuple(request.name for request in requests),
        )
        return len(rows)
    finally:
        conn.close()


def _validate_source_model(source_model: str) -> None:
    if not _SOURCE_MODEL_PATTERN.fullmatch(source_model):
        msg = f"Invalid source_model identifier: {source_model}"
        raise ValueError(msg)


def _ensure_stage_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS indicator_feature_stage (
            datetime TIMESTAMP NOT NULL,
            symbol VARCHAR NOT NULL,
            timeframe VARCHAR NOT NULL,
            source_model VARCHAR NOT NULL,
            feature_name VARCHAR NOT NULL,
            feature_id VARCHAR NOT NULL,
            parameter_hash VARCHAR NOT NULL,
            parameter_json VARCHAR NOT NULL,
            output_name VARCHAR NOT NULL,
            value DOUBLE,
            computed_at TIMESTAMP NOT NULL,
            computation_version VARCHAR NOT NULL,
            pandas_ta_classic_version VARCHAR NOT NULL,
            talib_available BOOLEAN NOT NULL,
            talib_version VARCHAR,
            talib_used BOOLEAN NOT NULL
        )
        """
    )


def _stage_rows(
    *,
    result_frame: Any,
    metadata: dict[str, object],
    symbol: str,
    timeframe: str,
    source_model: str,
    feature_name: str,
    output_names: tuple[str, ...],
    parameters: dict[str, object],
    computed_at: object,
) -> list[tuple[object, ...]]:
    parameter_json = canonical_parameter_json(parameters)
    param_hash = parameter_hash(parameters)
    stable_feature_id = feature_id(
        source_model=source_model,
        symbol=symbol,
        timeframe=timeframe,
        feature_name=feature_name,
        parameters=parameters,
        computation_version=COMPUTATION_VERSION,
    )
    rows: list[tuple[object, ...]] = []
    for record in result_frame[["datetime", *output_names]].to_dict("records"):
        for output_name in output_names:
            rows.append(
                (
                    record["datetime"],
                    symbol,
                    timeframe,
                    source_model,
                    feature_name,
                    stable_feature_id,
                    param_hash,
                    parameter_json,
                    output_name,
                    _normalize_value(record[output_name]),
                    computed_at,
                    COMPUTATION_VERSION,
                    str(metadata["pandas_ta_classic_version"]),
                    bool(metadata["talib_available"]),
                    metadata["talib_version"],
                    bool(metadata["talib_used"]),
                )
            )
    return rows


def _stable_computed_at(frame: Any) -> object:
    if frame.empty:
        return COMPUTATION_VERSION
    return frame["datetime"].max()


def _normalize_value(value: object) -> float | None:
    if not isinstance(value, int | float):
        return None
    if value != value:
        return None
    return float(value)


def _replace_stage_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[tuple[object, ...]],
    *,
    source_model: str,
    timeframe: str,
    feature_names: tuple[str, ...],
) -> None:
    conn.execute("BEGIN TRANSACTION")
    try:
        if feature_names:
            feature_placeholders = ", ".join("?" for _ in feature_names)
            conn.execute(
                f"""
                DELETE FROM indicator_feature_stage
                WHERE source_model = ?
                  AND timeframe = ?
                  AND feature_name IN ({feature_placeholders})
                """,  # nosec B608 — STAGE_COLUMNS es una constante interna de tupla
                [source_model, timeframe, *feature_names],
            )
        if rows:
            placeholders = ", ".join("?" for _ in STAGE_COLUMNS)
            columns = ", ".join(STAGE_COLUMNS)
            insert_sql = (
                f"INSERT INTO indicator_feature_stage ({columns}) "  # nosec B608
                f"VALUES ({placeholders})"
            )
            conn.executemany(
                insert_sql,
                rows,
            )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
