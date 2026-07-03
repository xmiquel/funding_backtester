"""Tests for the NinjaTrader Tick Data Pipeline.

Tests cover:
- event_ts derivation from raw timestamp parts (Spec: Staging View Normalization)
- Aggressor boolean logic (Spec: Materialized Tick Data Table)
- NT8 file format validation

These tests define expected transformation outputs per the spec.
The corresponding SQL models in analytics/ implement the same logic.
"""

import datetime
import pathlib

import duckdb
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_db():
    """In-memory DuckDB connection for transformation testing."""
    conn = duckdb.connect(":memory:")
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# event_ts derivation — staging view (Spec Requirement: Staging View
# Normalization, task 2.1 / 4.1)
#
# The raw timestamp format is:
#   YYYYMMDD HHMMSS.ticks
# where ticks are .NET ticks (100 ns resolution, 10M ticks = 1 second).
# ---------------------------------------------------------------------------


_TIMESTAMP_SQL = (
    "strptime(SUBSTRING(raw_timestamp, 1, 8)"
    " || ' ' || SUBSTRING(raw_timestamp, 10, 6), '%Y%m%d %H%M%S')"
    " + (CAST(COALESCE(NULLIF(SUBSTRING(raw_timestamp, 17), ''), '0')"
    " AS BIGINT) / 10000000.0) * INTERVAL '1 SECOND'"
)


def _staging_sql_table(source_table: str = "raw_ticks") -> str:
    """Return the staging transformation SQL matching stg_tick_data.sql."""
    return (
        "SELECT\n"
        "    SPLIT_PART(\n"
        "        REPLACE(REPLACE(filename, '.txt', ''), '/', '\\'),\n"
        "        '\\', -1\n"
        "    ) AS symbol,\n"
        f"    {_TIMESTAMP_SQL} AS event_ts,\n"
        "    bid, ask, last, volume\n"
        f"FROM {source_table}\n"
    )


class TestEventTsDerivation:
    """Verify symbol derivation from filename and event_ts from raw timestamp."""

    def test_symbol_and_event_ts_derived(self, memory_db: duckdb.DuckDBPyConnection):
        """Happy path: symbol from filename and event_ts from full precision."""
        memory_db.execute("""
            CREATE TABLE raw_ticks AS
            SELECT * FROM (VALUES
                ('20260315 093001.5000000', 4500.25, 4500.50, 4500.50, 1, 'MNQ0626.txt')
            ) t(raw_timestamp, bid, ask, last, volume, filename)
        """)

        row = memory_db.execute(_staging_sql_table()).fetchone()
        assert row is not None

        symbol, event_ts, bid, ask, last, volume = row

        assert symbol == "MNQ0626"
        assert event_ts == datetime.datetime(2026, 3, 15, 9, 30, 1, 500000)
        assert bid == 4500.25
        assert ask == 4500.50
        assert last == 4500.50
        assert volume == 1

    def test_null_subsecond_defaults_to_zero(self, memory_db: duckdb.DuckDBPyConnection):
        """Null/missing ticks part defaults to zero subsecond (no crash)."""
        memory_db.execute("""
            CREATE TABLE raw_ticks2 AS
            SELECT * FROM (VALUES
                ('20260315 093001', 4500.25, 4500.50, 4500.50, 1, 'TEST.txt')
            ) t(raw_timestamp, bid, ask, last, volume, filename)
        """)

        row = memory_db.execute(_staging_sql_table("raw_ticks2")).fetchone()
        assert row is not None

        _symbol, event_ts = row[0], row[1]
        assert event_ts == datetime.datetime(2026, 3, 15, 9, 30, 1, 0)

    def test_zero_subsecond_round_trip(self, memory_db: duckdb.DuckDBPyConnection):
        """Explicit .0000000 ticks produces zero subsecond."""
        memory_db.execute("""
            CREATE TABLE raw_ticks3 AS
            SELECT * FROM (VALUES
                ('20260315 093001.0000000', 4500.25, 4500.50, 4500.50, 1, 'TEST.txt')
            ) t(raw_timestamp, bid, ask, last, volume, filename)
        """)

        row = memory_db.execute(_staging_sql_table("raw_ticks3")).fetchone()
        assert row is not None

        event_ts = row[1]
        assert event_ts == datetime.datetime(2026, 3, 15, 9, 30, 1, 0)

    def test_filename_with_path(self, memory_db: duckdb.DuckDBPyConnection):
        """filename from DuckDB passthrough includes path; symbol extracted correctly."""
        for fname in (
            "MNQ0626.txt",
            "data/raw/MNQ0626.txt",
            r"data\raw\MNQ0626.txt",
        ):
            memory_db.execute(
                """
                CREATE TABLE raw_path AS
                SELECT * FROM (VALUES
                    ('20260315 093001.5000000', 4500.25, 4500.50, 4500.50, 1, ?)
                ) t(raw_timestamp, bid, ask, last, volume, filename)
            """,
                [fname],
            )

            symbol = memory_db.execute(_staging_sql_table("raw_path")).fetchone()[0]

            assert symbol == "MNQ0626", f"Failed for filename={fname!r}"

            memory_db.execute("DROP TABLE raw_path")


# ---------------------------------------------------------------------------
# Aggressor boolean logic — final table (Spec Requirement: Materialized Tick
# Data Table, task 2.2 / 4.2)
# ---------------------------------------------------------------------------


def _final_sql(staging_table: str = "stg_tick_data") -> str:
    """Return the final table SQL matching dt_tick_data.sql."""
    return f"""
        SELECT
            *,
            ask - bid AS spread,
            (bid + ask) / 2.0 AS mid,
            last >= ask AS is_aggressive_buy,
            last <= bid AS is_aggressive_sell
        FROM {staging_table}
    """


class TestAggressorLogic:
    """Verify derived columns in the final materialized table."""

    def test_aggressive_buy(self, memory_db: duckdb.DuckDBPyConnection):
        """last >= ask → is_aggressive_buy = true."""
        memory_db.execute("""
            CREATE TABLE stg_test1 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:01.5' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_final_sql("stg_test1")).fetchone()
        assert row is not None

        spread, mid, is_aggr_buy, is_aggr_sell = row[-4:]

        assert spread == pytest.approx(0.25)
        assert mid == pytest.approx(4500.375)
        assert is_aggr_buy is True
        assert is_aggr_sell is False

    def test_aggressive_sell(self, memory_db: duckdb.DuckDBPyConnection):
        """last <= bid → is_aggressive_sell = true."""
        memory_db.execute("""
            CREATE TABLE stg_test2 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:01.5' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.25, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_final_sql("stg_test2")).fetchone()
        assert row is not None

        spread, mid, is_aggr_buy, is_aggr_sell = row[-4:]

        assert spread == pytest.approx(0.25)
        assert mid == pytest.approx(4500.375)
        assert is_aggr_buy is False
        assert is_aggr_sell is True

    def test_neutral_tick(self, memory_db: duckdb.DuckDBPyConnection):
        """last between bid and ask → both flags false."""
        memory_db.execute("""
            CREATE TABLE stg_test3 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:01.5' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.35, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_final_sql("stg_test3")).fetchone()
        assert row is not None

        spread, mid, is_aggr_buy, is_aggr_sell = row[-4:]

        assert spread == pytest.approx(0.25)
        assert mid == pytest.approx(4500.375)
        assert is_aggr_buy is False
        assert is_aggr_sell is False

    def test_aggressive_buy_and_sell_same_tick(self, memory_db: duckdb.DuckDBPyConnection):
        """last == bid == ask (rare) → both flags true."""
        memory_db.execute("""
            CREATE TABLE stg_test4 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:01.5' AS TIMESTAMP),
                 4500.25, 4500.25, 4500.25, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_final_sql("stg_test4")).fetchone()
        assert row is not None

        spread, mid, is_aggr_buy, is_aggr_sell = row[-4:]

        assert spread == pytest.approx(0.0)
        assert mid == pytest.approx(4500.25)
        assert is_aggr_buy is True  # >=
        assert is_aggr_sell is True  # <=


# ---------------------------------------------------------------------------
# NT8 file validation — loader script (Spec Requirement: Raw Source File
# Layout, task 3.3 / 4.3)
# ---------------------------------------------------------------------------


class TestNt8FileValidation:
    """Verify NT8 file format detection and validation."""

    VALID_HEADER_LINE = "20260315 093001.5000000;4500.25;4500.50;4500.50;1\n"

    def _write_file(self, tmp: pathlib.Path, name: str, content: str) -> pathlib.Path:
        p = tmp / name
        p.write_text(content)
        return p

    def test_valid_line_parse(self):
        """A well-formed NT8 line returns expected tokens."""
        from funding_backtester.scripts.load_ticks import parse_tick_line

        tokens = parse_tick_line(self.VALID_HEADER_LINE)
        assert tokens is not None
        assert tokens["raw_timestamp"] == "20260315 093001.5000000"
        assert tokens["bid"] == 4500.25
        assert tokens["ask"] == 4500.50
        assert tokens["last"] == 4500.50
        assert tokens["volume"] == 1

    def test_valid_line_rstrip(self):
        """Trailing whitespace and newlines handled."""
        from funding_backtester.scripts.load_ticks import parse_tick_line

        tokens = parse_tick_line("20260315 093001.5000000;4500.25;4500.50;4500.50;1  \n")
        assert tokens is not None
        assert tokens["last"] == 4500.50

    def test_malformed_line_too_few_columns(self):
        """Line with fewer than 5 columns returns None."""
        from funding_backtester.scripts.load_ticks import parse_tick_line

        assert parse_tick_line("abc;123;456\n") is None

    def test_malformed_line_non_numeric_price(self):
        """Line with non-numeric price returns None."""
        from funding_backtester.scripts.load_ticks import parse_tick_line

        assert parse_tick_line("20260315 093001;abc;4500.50;4500.50;1\n") is None

    def test_empty_line(self):
        """Empty line returns None."""
        from funding_backtester.scripts.load_ticks import parse_tick_line

        assert parse_tick_line("") is None
        assert parse_tick_line("\n") is None
        assert parse_tick_line("   \n") is None

    def test_scan_directory_with_valid_files(self, tmp_path: pathlib.Path):
        """Scanning a directory with valid files returns discovered paths."""
        from funding_backtester.scripts.load_ticks import scan_tick_files

        self._write_file(tmp_path, "MNQ0626.txt", self.VALID_HEADER_LINE)
        self._write_file(tmp_path, "ES0626.txt", self.VALID_HEADER_LINE)

        files = scan_tick_files(str(tmp_path))
        names = {p.name for p in files}
        assert names == {"MNQ0626.txt", "ES0626.txt"}

    def test_scan_directory_empty(self, tmp_path: pathlib.Path):
        """Empty scan raises expected condition."""
        from funding_backtester.scripts.load_ticks import scan_tick_files

        with pytest.raises(RuntimeError, match="No tick files found"):
            scan_tick_files(str(tmp_path))

    def test_scan_nonexistent_directory(self):
        """Missing directory raises RuntimeError."""
        from funding_backtester.scripts.load_ticks import scan_tick_files

        with pytest.raises(RuntimeError, match="does not exist"):
            scan_tick_files("/nonexistent/path/ticks")
