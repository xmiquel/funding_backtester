"""NinjaTrader Tick Data Pipeline — Loader Script.

Ingests NT8 Tick Replay TXT exports into DuckDB, bootstraps the raw view,
and invokes dbt for staging/final materialization.

Usage:
    uv run python -m funding_backtester.scripts.load_ticks <data_dir>

The data directory should contain `<symbol>.txt` files in NT8 export format.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess  # nosec B404
import sys

import duckdb


def parse_tick_line(line: str) -> dict[str, str | float | int] | None:
    """Parse a single NT8 Tick Replay line into a dict of typed values.

    Expected format (semicolon-delimited):
        raw_timestamp;ask;bid;last;volume

    Returns None if the line is empty or malformed.
    """
    stripped = line.strip()
    if not stripped:
        return None

    parts = stripped.split(";")
    if len(parts) < 5:
        return None

    raw_ts, ask_str, bid_str, last_str, vol_str = parts[:5]

    try:
        bid = float(bid_str)
        ask = float(ask_str)
        last = float(last_str)
        volume = int(vol_str)
    except (ValueError, TypeError):
        return None

    return {
        "raw_timestamp": raw_ts,
        "bid": bid,
        "ask": ask,
        "last": last,
        "volume": volume,
    }


def scan_tick_files(data_dir: str) -> list[pathlib.Path]:
    """Scan *data_dir* for ``.txt`` tick files.

    Returns a sorted list of file paths.

    Raises:
        RuntimeError: if the directory does not exist or contains no tick files.
    """
    path = pathlib.Path(data_dir)
    if not path.is_dir():
        raise RuntimeError(f"Tick data directory does not exist: {data_dir}")

    files = sorted(path.glob("*.txt"))
    if not files:
        raise RuntimeError(f"No tick files found in {data_dir}")

    return files


def create_raw_view(conn: duckdb.DuckDBPyConnection, data_dir: str) -> None:
    """Create or replace the ``raw_ticks`` view over ``*.txt`` in *data_dir*.

    The view uses ``read_csv_auto`` with filename passthrough and exposes
    five columns: raw_timestamp, ask, bid, last, volume, and filename.
    """
    glob_pattern = str(pathlib.Path(data_dir, "*.txt").resolve())
    conn.execute(
        f"""
        CREATE OR REPLACE VIEW raw_ticks AS
        SELECT * FROM read_csv_auto(
            '{glob_pattern}',
            delim=';',
            header=false,
            columns={{
                'raw_timestamp': 'VARCHAR',
                'ask': 'DOUBLE',
                'bid': 'DOUBLE',
                'last': 'DOUBLE',
                'volume': 'BIGINT'
            }},
            filename=true
        )
        """
    )


def bootstrap_duckdb(db_path: str, data_dir: str) -> duckdb.DuckDBPyConnection:
    """Connect to (or create) the DuckDB database at *db_path* and bootstrap
    the ``raw_ticks`` view over *data_dir*.

    Returns the open connection.
    """
    conn = duckdb.connect(db_path)
    create_raw_view(conn, data_dir)
    return conn


def run_dbt(project_dir: str) -> int:
    """Run ``dbt build`` in *project_dir*.

    Returns the subprocess return code.
    """
    result = subprocess.run(  # nosec B603 B607
        ["uv", "run", "dbt", "build"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    return result.returncode


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Load NinjaTrader tick data into DuckDB and run dbt pipeline."
    )
    parser.add_argument(
        "data_dir",
        nargs="?",
        default="data/raw",
        help="Directory containing NT8 tick export .txt files (default: data/raw)",
    )
    parser.add_argument(
        "--duckdb-path",
        default="data/ticks.duckdb",
        help="Path to DuckDB database file (default: data/ticks.duckdb)",
    )
    parser.add_argument(
        "--dbt-project-dir",
        default="analytics",
        help="Path to dbt project directory (default: analytics)",
    )
    parser.add_argument(
        "--skip-dbt",
        action="store_true",
        help="Skip dbt build after loading data",
    )

    args = parser.parse_args()

    # 1. Scan for source files
    try:
        files = scan_tick_files(args.data_dir)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Discovered {len(files)} tick file(s) in {args.data_dir}")

    # 2. Bootstrap DuckDB + raw view
    conn = bootstrap_duckdb(args.duckdb_path, args.data_dir)
    conn.close()
    print(f"DuckDB database ready at {args.duckdb_path}")

    # 3. Run dbt pipeline
    if args.skip_dbt:
        print("Skipping dbt build (--skip-dbt)")
    else:
        print("Running dbt build...")
        rc = run_dbt(args.dbt_project_dir)
        if rc != 0:
            print(f"dbt build failed (exit code {rc})", file=sys.stderr)
            return rc
        print("dbt build completed successfully")

    return 0


if __name__ == "__main__":
    sys.exit(main())
