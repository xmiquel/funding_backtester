"""Vectorbt-compatible loader for persisted indicator features.

Loads close prices and indicator features from DuckDB into datetime-aligned
``pd.Series`` / ``pd.DataFrame`` tuples usable directly by vectorbt.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd  # type: ignore[import-untyped]
# pandas stubs not installed; duckdb.df() returns untyped DataFrame

_SOURCE_MODEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FEATURE_TABLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(pattern: re.Pattern[str], name: str, label: str) -> None:
    if not pattern.fullmatch(name):
        msg = f"Invalid {label}: {name!r}"
        raise ValueError(msg)


def load_features(
    database_path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    source_model: str = "ohlcv_15s",
    feature_names: tuple[str, ...] | None = None,
    feature_table: str = "indicator_feature_stage",
) -> tuple[pd.Series, pd.DataFrame]:
    """Load close prices and aligned indicator features for vectorbt.

    Args:
        database_path: Path to the DuckDB database file.
        symbol: Trading symbol to filter (e.g. ``"ES"``).
        timeframe: Timeframe string (e.g. ``"15s"``).
        source_model: Source OHLCV model name used to fetch close prices.
        feature_names: Optional subset of feature names. When *None* all
            available features for the symbol/timeframe are returned.
        feature_table: Name of the DuckDB table or view holding long-form
            indicator feature rows.

    Returns:
        Tuple of ``(close, features)``:
        - **close**: ``pd.Series`` indexed by ``datetime``, name ``"close"``.
        - **features**: ``pd.DataFrame`` indexed by ``datetime`` with columns
          ``{feature_name}_{output_name}_{parameter_hash}``.

    Raises:
        RuntimeError: If the feature table does not exist in the database.
    """
    _validate_identifier(_SOURCE_MODEL_PATTERN, source_model, "source_model")
    _validate_identifier(_FEATURE_TABLE_PATTERN, feature_table, "feature_table")
    conn = duckdb.connect(str(database_path))
    try:
        _assert_feature_table_exists(conn, feature_table)
        close = _load_close(conn, source_model, symbol)
        features = _load_feature_frame(conn, symbol, timeframe, feature_table, feature_names)
        common_idx = close.index.intersection(features.index)
        return close.loc[common_idx], features.loc[common_idx]
    finally:
        conn.close()


def _assert_feature_table_exists(
    conn: duckdb.DuckDBPyConnection,
    feature_table: str,
) -> None:
    """Raise ``RuntimeError`` if the feature table is missing."""
    tables = conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_name = ?",
        [feature_table],
    ).fetchall()
    if not tables:
        msg = (
            f"Feature table {feature_table!r} not found. "
            "Build features first with build_indicator_feature_stage()."
        )
        raise RuntimeError(msg)


def _load_close(
    conn: duckdb.DuckDBPyConnection,
    source_model: str,
    symbol: str,
) -> pd.Series:
    """Load close prices from the OHLCV source model."""
    df = conn.execute(
        f"SELECT datetime, close FROM {source_model} WHERE symbol = ? ORDER BY datetime",  # nosec B608
        [symbol],
    ).df()
    if df.empty:
        return pd.Series([], dtype="float64", name="close")
    return pd.Series(
        df["close"].values,
        index=pd.DatetimeIndex(df["datetime"]),
        name="close",
    )


def _load_feature_frame(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    timeframe: str,
    feature_table: str,
    feature_names: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Load and pivot indicator features into a wide DataFrame."""
    if feature_names:
        placeholders = ", ".join("?" for _ in feature_names)
        params: list[object] = [symbol, timeframe, *feature_names]
        sql = f"""
            SELECT datetime, feature_name, output_name, parameter_hash, value
            FROM {feature_table}
            WHERE symbol = ? AND timeframe = ? AND feature_name IN ({placeholders})
            ORDER BY datetime
        """  # nosec B608 — feature_table validated by _validate_identifier regex
    else:
        params = [symbol, timeframe]
        sql = f"""
            SELECT datetime, feature_name, output_name, parameter_hash, value
            FROM {feature_table}
            WHERE symbol = ? AND timeframe = ?
            ORDER BY datetime
        """  # nosec B608 — feature_table validated by _validate_identifier regex

    df = conn.execute(sql, params).df()
    if df.empty:
        return pd.DataFrame()

    col = df["feature_name"] + "_" + df["output_name"] + "_" + df["parameter_hash"]
    pivoted = df.assign(feature_col=col).pivot_table(
        index="datetime",
        columns="feature_col",
        values="value",
        aggfunc="first",
    )
    pivoted.index = pd.DatetimeIndex(pivoted.index)
    pivoted.index.name = "datetime"

    # When all feature values are NaN the pivot produces zero columns
    # and an empty index. Build expected columns + index from source rows
    # so callers get aligned output.
    if pivoted.shape[1] == 0 and len(df) > 0:
        expected_cols = list(dict.fromkeys(col.tolist()))
        dt_index = pd.DatetimeIndex(df["datetime"].unique())
        dt_index.name = "datetime"
        pivoted = pd.DataFrame(
            {c: [pd.NA] * len(dt_index) for c in expected_cols},
            index=dt_index,
        )

    return pivoted
