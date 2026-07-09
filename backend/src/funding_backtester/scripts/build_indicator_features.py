"""Script CLI de construcción de *indicator features*.

Calcula *indicator features* catalogadas desde marts OHLCV persistidos en
DuckDB, genera filas largas de features mediante ``build_indicator_feature_stage``
y, de forma opcional, ejecuta el flujo de dbt para materializar
``indicator_features``.

Uso:
    uv run python -m funding_backtester.scripts.build_indicator_features
    uv run python -m funding_backtester.scripts.build_indicator_features \
        --feature-names sma,ema,rsi \
        --source-model ohlcv_15s \
        --timeframe 15s \
        --skip-dbt
"""

from __future__ import annotations

import argparse
import os
import pathlib
import subprocess  # nosec B404
import sys

from funding_backtester.config import settings
from funding_backtester.indicators.duckdb_io import build_indicator_feature_stage


def _default_dbt_project_dir() -> pathlib.Path:
    """Devuelve el directorio del proyecto dbt del repositorio."""
    return pathlib.Path(__file__).resolve().parents[4] / "analytics"


def build(
    database_path: str | pathlib.Path,
    *,
    source_model: str,
    timeframe: str,
    feature_names: tuple[str, ...],
    dbt_project_dir: str | pathlib.Path | None = None,
    skip_dbt: bool = False,
) -> int:
    """Calcula *indicator features* desde OHLCV en DuckDB y, opcionalmente, ejecuta dbt.

    Argumentos:
        database_path: Ruta al archivo de base de datos DuckDB.
        source_model: Nombre del modelo OHLCV de dbt (por ejemplo, ``ohlcv_15s``).
        timeframe: Etiqueta de timeframe para la persistencia (por ejemplo, ``15s``).
        feature_names: Nombres catalogados de *indicator features* a calcular.
        dbt_project_dir: Ruta al directorio del proyecto dbt. Si se omite, usa el
            directorio ``analytics`` del repositorio relativo a este script.
        skip_dbt: Si es True, omite la ejecución de dbt después de generar el stage.

    Devuelve:
        Cantidad de filas escritas en el stage de *indicator features*.

    Lanza:
        ValueError: Si el identificador de source_model no es válido.
        subprocess.CalledProcessError: Si falla la construcción de dbt.
    """
    resolved_database_path = pathlib.Path(database_path).resolve()
    count = build_indicator_feature_stage(
        resolved_database_path,
        source_model=source_model,
        timeframe=timeframe,
        feature_names=feature_names,
    )

    print(
        f"Se escribieron {count} fila(s) del stage de indicator features "
        f"para {', '.join(feature_names)} "
        f"desde {source_model} ({timeframe})"
    )

    if not skip_dbt:
        print("Ejecutando dbt build...")
        dbt_dir = (
            _default_dbt_project_dir()
            if dbt_project_dir is None
            else pathlib.Path(dbt_project_dir).resolve()
        )
        env = os.environ.copy()
        env["DBT_DUCKDB_PATH"] = str(resolved_database_path)
        result = subprocess.run(  # nosec B603 B607
            ["uv", "run", "dbt", "build", "--select", "indicator_features"],
            cwd=str(dbt_dir),
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            msg = f"dbt build falló (código de salida {result.returncode})"
            raise subprocess.CalledProcessError(result.returncode, result.args, msg)
        print("dbt build se completó correctamente")
    else:
        print("Omitiendo dbt build (--skip-dbt)")

    return count


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI para construcciones de *indicator features*.

    Devuelve:
        Código de salida (0 si fue exitoso, 1 si falló).
    """
    parser = argparse.ArgumentParser(
        description="Calcula indicator features desde OHLCV en DuckDB y ejecuta el flujo de dbt."
    )
    parser.add_argument(
        "--duckdb-path",
        default=settings.duckdb_path,
        help="Ruta al archivo de base de datos DuckDB (valor predeterminado: desde settings)",
    )
    parser.add_argument(
        "--source-model",
        default="ohlcv_15s",
        help="Nombre del modelo fuente OHLCV de dbt (valor predeterminado: ohlcv_15s)",
    )
    parser.add_argument(
        "--timeframe",
        default="15s",
        help="Etiqueta de timeframe para las features persistidas (valor predeterminado: 15s)",
    )
    parser.add_argument(
        "--feature-names",
        required=True,
        help=(
            "Lista separada por comas de nombres catalogados de indicator features "
            "(por ejemplo, sma,ema,rsi)"
        ),
    )
    parser.add_argument(
        "--dbt-project-dir",
        default=None,
        help=(
            "Ruta al directorio del proyecto dbt (valor predeterminado: "
            "analytics/ del repositorio)"
        ),
    )
    parser.add_argument(
        "--skip-dbt",
        action="store_true",
        help="Omitir dbt build después de generar el stage de features",
    )

    args = parser.parse_args(argv)

    feature_names = tuple(name.strip() for name in args.feature_names.split(",") if name.strip())
    if not feature_names:
        print("Error: --feature-names debe especificar al menos una feature", file=sys.stderr)
        return 1

    try:
        build(
            database_path=args.duckdb_path,
            source_model=args.source_model,
            timeframe=args.timeframe,
            feature_names=feature_names,
            dbt_project_dir=args.dbt_project_dir,
            skip_dbt=args.skip_dbt,
        )
    except (ValueError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error: no se pudo ejecutar dbt build mediante uv: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
