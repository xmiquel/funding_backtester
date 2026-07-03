"""Integration tests for the dbt tick data pipeline.

Tests run a full ``dbt build`` against a temporary DuckDB database using
committed fixture TXT files from ``tests/data/``, then verify the materialized
outputs against expected row counts and derived column values.

These tests are NOT unit tests — they exercise the full dbt DAG end-to-end
(source → staging → final → manifest) on every run. They are intentionally
separate from ``test_tick_pipeline.py`` (unit tests) and are slower.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import duckdb
import pytest

# Path to the committed test fixture directory
FIXTURE_DIR = pathlib.Path(__file__).parent / "data"
# Path to the dbt project directory
DBT_PROJECT = pathlib.Path(__file__).parent.parent.parent / "analytics"

# Expected row counts per fixture file
EXPECTED_ROWS = {
    "MNQ0626": 5,
    "ES0626": 2,
}
TOTAL_ROWS = sum(EXPECTED_ROWS.values())  # 7


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def dbt_env(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Set up a temporary DuckDB + run ``dbt build``.

    Creates a temporary DuckDB database, bootstraps the ``raw_ticks`` view
    pointing at the committed fixture TXT files, then runs ``dbt build``.

    Returns the path to the DuckDB database file for test queries.
    """
    tmp = tmp_path_factory.mktemp("dbt_test")
    db_path = tmp / "ticks.duckdb"

    # Create absolute path to fixture directory (dbt CWD is analytics/)
    fixture_abs = FIXTURE_DIR.resolve()
    pattern = str(fixture_abs / "*.txt")

    # Bootstrap DuckDB with raw view over fixture files
    conn = duckdb.connect(str(db_path))
    conn.execute(
        f"""
        CREATE OR REPLACE VIEW raw_ticks AS
        SELECT * FROM read_csv_auto(
            '{pattern}',
            delim=';',
            header=false,
            columns={{
                'raw_timestamp': 'VARCHAR',
                'bid': 'DOUBLE',
                'ask': 'DOUBLE',
                'last': 'DOUBLE',
                'volume': 'BIGINT'
            }},
            filename=true
        )
        """
    )
    conn.close()

    # Run dbt build pointing at the temp DuckDB
    env = os.environ.copy()
    env["DBT_DUCKDB_PATH"] = str(db_path)

    result = subprocess.run(
        ["uv", "run", "dbt", "build"],
        cwd=str(DBT_PROJECT.resolve()),
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("--- dbt stdout ---")
        print(result.stdout)
        print("--- dbt stderr ---")
        print(result.stderr)
        pytest.fail(f"dbt build failed (exit {result.returncode})")

    return str(db_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDbtBuild:
    """Verify the full dbt pipeline produces correct output."""

    def test_raw_ticks_view_parses_fixtures(self, dbt_env: str) -> None:
        """Raw view serves all rows from fixture TXT files."""
        conn = duckdb.connect(dbt_env)
        try:
            row_count = conn.execute(
                "SELECT COUNT(*) FROM raw_ticks"
            ).fetchone()[0]
            assert row_count == TOTAL_ROWS, (
                f"Expected {TOTAL_ROWS} raw rows, got {row_count}"
            )
        finally:
            conn.close()

    def test_stg_tick_data_row_count(self, dbt_env: str) -> None:
        """Staging view has all rows from raw view."""
        conn = duckdb.connect(dbt_env)
        try:
            row_count = conn.execute(
                "SELECT COUNT(*) FROM stg_tick_data"
            ).fetchone()[0]
            assert row_count == TOTAL_ROWS, (
                f"Expected {TOTAL_ROWS} staging rows, got {row_count}"
            )
        finally:
            conn.close()

    def test_dt_tick_data_row_count(self, dbt_env: str) -> None:
        """Final materialized table has all rows."""
        conn = duckdb.connect(dbt_env)
        try:
            row_count = conn.execute(
                "SELECT COUNT(*) FROM dt_tick_data"
            ).fetchone()[0]
            assert row_count == TOTAL_ROWS, (
                f"Expected {TOTAL_ROWS} final rows, got {row_count}"
            )
        finally:
            conn.close()

    def test_symbol_derived_from_filename(self, dbt_env: str) -> None:
        """Symbol column correctly derived from source filename."""
        conn = duckdb.connect(dbt_env)
        try:
            rows = conn.execute(
                "SELECT DISTINCT symbol FROM stg_tick_data ORDER BY symbol"
            ).fetchall()
            symbols = {r[0] for r in rows}
            expected = {"MNQ0626", "ES0626"}
            assert symbols == expected, f"Expected {expected}, got {symbols}"
        finally:
            conn.close()

    def test_event_ts_has_microsecond_precision(self, dbt_env: str) -> None:
        """event_ts includes microseconds from .NET tick conversion."""
        conn = duckdb.connect(dbt_env)
        try:
            rows = conn.execute(
                "SELECT symbol, event_ts FROM stg_tick_data ORDER BY symbol, event_ts"
            ).fetchall()
            # MNQ0626 row 1: 20260315 093001.5000000 → 500ms = 500000µs
            mnq_rows = [r for r in rows if r[0] == "MNQ0626"]
            assert len(mnq_rows) == 5
            first_ts = mnq_rows[0][1]
            assert first_ts.microsecond == 500000, (
                f"Expected 500000 µs, got {first_ts.microsecond}"
            )
        finally:
            conn.close()

    def test_derived_columns_computed(self, dbt_env: str) -> None:
        """spread, mid, and aggressor flags are correctly computed."""
        conn = duckdb.connect(dbt_env)
        try:
            # MNQ0626 first row: bid=4500.25, ask=4500.50, last=4500.50
            row = conn.execute(
                """
                SELECT spread, mid, is_aggressive_buy, is_aggressive_sell
                FROM dt_tick_data
                WHERE symbol = 'MNQ0626'
                ORDER BY event_ts
                LIMIT 1
                """
            ).fetchone()
            assert row is not None
            spread, mid, buy, sell = row
            assert spread == 0.25, f"Expected spread 0.25, got {spread}"
            assert mid == 4500.375, f"Expected mid 4500.375, got {mid}"
            assert buy is True, "Expected aggressive buy"
            assert sell is False, "Expected not aggressive sell"
        finally:
            conn.close()

    def test_aggressive_sell_detected(self, dbt_env: str) -> None:
        """Tick at bid triggers is_aggressive_sell."""
        conn = duckdb.connect(dbt_env)
        try:
            # MNQ0626 second row: bid=4500.25, ask=4500.50, last=4500.25
            row = conn.execute(
                """
                SELECT is_aggressive_buy, is_aggressive_sell
                FROM dt_tick_data
                WHERE symbol = 'MNQ0626'
                ORDER BY event_ts
                OFFSET 1 LIMIT 1
                """
            ).fetchone()
            assert row is not None
            buy, sell = row
            assert buy is False, "Expected not aggressive buy"
            assert sell is True, "Expected aggressive sell"
        finally:
            conn.close()

    def test_manifest_records_filenames(self, dbt_env: str) -> None:
        """tick_load_manifest contains all fixture filenames."""
        conn = duckdb.connect(dbt_env)
        try:
            rows = conn.execute(
                "SELECT filename FROM tick_load_manifest ORDER BY filename"
            ).fetchall()
            filenames = [r[0] for r in rows]
            assert any("MNQ0626" in f for f in filenames), (
                f"MNQ0626 not in {filenames}"
            )
            assert any("ES0626" in f for f in filenames), (
                f"ES0626 not in {filenames}"
            )
        finally:
            conn.close()

    def test_manifest_has_loaded_at(self, dbt_env: str) -> None:
        """tick_load_manifest has non-null timestamps."""
        conn = duckdb.connect(dbt_env)
        try:
            result = conn.execute(
                "SELECT COUNT(*) FROM tick_load_manifest WHERE loaded_at IS NULL"
            ).fetchone()[0]
            assert result == 0, f"Expected 0 null loaded_at, got {result}"
        finally:
            conn.close()

    def test_volume_preserved(self, dbt_env: str) -> None:
        """Volume column values are preserved through the pipeline."""
        conn = duckdb.connect(dbt_env)
        try:
            rows = conn.execute(
                """
                SELECT symbol, volume FROM dt_tick_data
                ORDER BY symbol, event_ts
                """
            ).fetchall()
            # MNQ0626 volumes: 1, 1, 2, 3, 4
            mnq = [r[1] for r in rows if r[0] == "MNQ0626"]
            assert mnq == [1, 1, 2, 3, 4], f"Unexpected MNQ volumes: {mnq}"
            # ES0626 volumes: 1, 2
            es = [r[1] for r in rows if r[0] == "ES0626"]
            assert es == [1, 2], f"Unexpected ES volumes: {es}"
        finally:
            conn.close()


class TestDbtBuildIdempotent:
    """Verify a second dbt build produces identical results."""

    def test_idempotent_run_same_row_count(self, dbt_env: str) -> None:
        """Second dbt build produces same row count — no duplicates."""
        # Re-run dbt build using the same database (already in dbt_env)
        db_path = dbt_env

        # Set up env for idempotent re-run
        env = os.environ.copy()
        env["DBT_DUCKDB_PATH"] = db_path

        result = subprocess.run(
            ["uv", "run", "dbt", "build"],
            cwd=str(DBT_PROJECT.resolve()),
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Second dbt build failed:\n{result.stderr}"
        )

        conn = duckdb.connect(db_path)
        try:
            row_count = conn.execute(
                "SELECT COUNT(*) FROM dt_tick_data"
            ).fetchone()[0]
            assert row_count == TOTAL_ROWS, (
                f"Expected {TOTAL_ROWS} rows after re-run, got {row_count}"
            )
        finally:
            conn.close()
