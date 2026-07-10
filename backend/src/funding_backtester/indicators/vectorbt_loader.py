"""Loader compatible con vectorbt para features de indicadores persistidas.

Carga precios de cierre y features de indicadores desde DuckDB en tuplas
``pd.Series`` / ``pd.DataFrame`` alineadas por datetime y listas para vectorbt.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd  # type: ignore[import-untyped]

# No están instalados los stubs de pandas; duckdb.df() devuelve un DataFrame sin tipado.

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
    """Carga precios de cierre y features de indicadores alineadas para vectorbt.

    Args:
        database_path: Ruta al archivo de base de datos DuckDB.
        symbol: Símbolo de trading a filtrar (por ejemplo, ``"ES"``).
        timeframe: Cadena de marco temporal (por ejemplo, ``"15s"``).
        source_model: Nombre del modelo OHLCV de origen usado para obtener los precios de cierre.
        feature_names: Subconjunto opcional de nombres de features. Cuando es *None*,
            se devuelven todas las features disponibles para el símbolo y el timeframe.
        feature_table: Nombre de la tabla o vista de DuckDB que contiene filas largas de
            features de indicadores.

    Returns:
        Tupla ``(close, features)``:
        - **close**: ``pd.Series`` indexada por ``datetime``, con nombre ``"close"``.
        - **features**: ``pd.DataFrame`` indexado por ``datetime`` con columnas
          ``{feature_name}_{output_name}_{parameter_hash}``.

    Raises:
        RuntimeError: Si la tabla de features no existe en la base de datos.
    """
    _validate_identifier(_SOURCE_MODEL_PATTERN, source_model, "source_model")
    _validate_identifier(_FEATURE_TABLE_PATTERN, feature_table, "feature_table")
    conn = duckdb.connect(str(database_path))
    try:
        _assert_feature_table_exists(conn, feature_table)
        close = _load_close(conn, source_model, symbol)
        features = _load_feature_frame(
            conn,
            source_model,
            symbol,
            timeframe,
            feature_table,
            feature_names,
        )
        common_idx = close.index.intersection(features.index)
        return close.loc[common_idx], features.loc[common_idx]
    finally:
        conn.close()


def _assert_feature_table_exists(
    conn: duckdb.DuckDBPyConnection,
    feature_table: str,
) -> None:
    """Lanza ``RuntimeError`` si falta la tabla de features."""
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
    """Carga los precios de cierre desde el modelo OHLCV de origen."""
    query = f"SELECT datetime, close FROM {source_model} WHERE symbol = ? ORDER BY datetime"
    df = conn.execute(
        query,  # nosec B608 — source_model validado por _validate_identifier
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
    source_model: str,
    symbol: str,
    timeframe: str,
    feature_table: str,
    feature_names: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Carga y pivotea las features de indicadores en un DataFrame ancho."""
    if feature_names:
        placeholders = ", ".join("?" for _ in feature_names)
        params: list[object] = [source_model, symbol, timeframe, *feature_names]
        sql = f"""
            SELECT datetime, feature_name, output_name, parameter_hash, value
            FROM {feature_table}
            WHERE source_model = ? AND symbol = ? AND timeframe = ?
              AND feature_name IN ({placeholders})
            ORDER BY datetime
        """  # nosec B608 — feature_table validada por la expresión regular de _validate_identifier
    else:
        params = [source_model, symbol, timeframe]
        sql = f"""
            SELECT datetime, feature_name, output_name, parameter_hash, value
            FROM {feature_table}
            WHERE source_model = ? AND symbol = ? AND timeframe = ?
            ORDER BY datetime
        """  # nosec B608 — feature_table validada por la expresión regular de _validate_identifier

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

    # Cuando todos los valores de las features son NaN, el pivot produce cero columnas
    # y un índice vacío. Construimos las columnas esperadas y el índice desde las filas
    # de origen para que los callers reciban una salida alineada.
    if pivoted.shape[1] == 0 and len(df) > 0:
        expected_cols = list(dict.fromkeys(col.tolist()))
        dt_index = pd.DatetimeIndex(df["datetime"].unique())
        dt_index.name = "datetime"
        pivoted = pd.DataFrame(
            {c: [pd.NA] * len(dt_index) for c in expected_cols},
            index=dt_index,
        )

    return pivoted
