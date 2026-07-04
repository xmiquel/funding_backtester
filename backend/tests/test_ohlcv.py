"""Tests for the OHLCV 15-second and multi-timeframe aggregation pipeline.

Tests cover:
- 15-second bucket alignment formula (Spec: 15-Second Bucket Alignment)
- Multi-timeframe bucket alignment (Spec: Multi-Timeframe OHLCV)
- OHLCVBar Pydantic schema serialization (Spec: API Response Schema)
- Integration test for GET /api/v1/ohlcv endpoint (Spec: API Query by Symbol)
- Multi-granularity API parameter (Spec: API Granularity Parameter)

Layer strategy: unit tests for pure logic (bucket alignment, schema) use
DuckDB in-memory; integration tests use httpx AsyncClient.
"""

from __future__ import annotations

from datetime import datetime as dt

import pytest
from pydantic import ValidationError

from funding_backtester.schemas.api import OHLCVBar

# ---------------------------------------------------------------------------
# 15-Second Bucket Alignment
# Spec: Requirement "15-Second Bucket Alignment"
# Formula: date_trunc('second', event_ts) - INTERVAL (EXTRACT(SECOND FROM
#          event_ts) % 15) SECOND
# ---------------------------------------------------------------------------


def _bucket_sql(source_table: str = "test_ticks") -> str:
    """Return the 15s bucket alignment SQL matching ohlcv_15s.sql."""
    return f"""
        SELECT
            date_trunc('second', event_ts)
              - INTERVAL (EXTRACT(SECOND FROM event_ts) % 15) SECOND AS datetime,
            symbol, last, bid, ask, volume
        FROM {source_table}
    """


def _ohlcv_sql(source_table: str = "bucketed") -> str:
    """Return the full OHLCV aggregation SQL matching ohlcv_15s.sql."""
    return f"""
        WITH bucketed AS (
            SELECT
                date_trunc('second', event_ts)
                  - INTERVAL (EXTRACT(SECOND FROM event_ts) % 15) SECOND AS datetime,
                symbol, last, bid, ask, volume,
                ROW_NUMBER() OVER (PARTITION BY symbol, datetime ORDER BY event_ts) AS rn_asc,
                ROW_NUMBER() OVER (PARTITION BY symbol, datetime ORDER BY event_ts DESC) AS rn_desc
            FROM {source_table}
        )
        SELECT
            datetime, symbol,
            MAX(CASE WHEN rn_asc = 1 THEN last END) AS open,
            MAX(last) AS high,
            MIN(last) AS low,
            MAX(CASE WHEN rn_desc = 1 THEN last END) AS close,
            SUM(volume) AS volume,
            MAX(CASE WHEN rn_asc = 1 THEN bid END) AS bid_open,
            MAX(bid) AS bid_high,
            MIN(bid) AS bid_low,
            MAX(CASE WHEN rn_desc = 1 THEN bid END) AS bid_close,
            MAX(CASE WHEN rn_asc = 1 THEN ask END) AS ask_open,
            MAX(ask) AS ask_high,
            MIN(ask) AS ask_low,
            MAX(CASE WHEN rn_desc = 1 THEN ask END) AS ask_close
        FROM bucketed
        GROUP BY datetime, symbol
    """


class Test15sBucketAlignment:
    """Verify 15-second bucket alignment formula (Spec: 15-Second Bucket Alignment)."""

    def test_tick_at_exact_boundary(self, memory_db):
        """Tick at 2026-03-15 09:30:00.000 → bucket 2026-03-15 09:30:00."""
        memory_db.execute("""
            CREATE TABLE test_ticks AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:00.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_bucket_sql()).fetchone()
        assert row is not None
        bucket_dt = row[0]

        expected = dt(2026, 3, 15, 9, 30, 0)
        assert bucket_dt == expected, f"Expected bucket {expected}, got {bucket_dt}"

    def test_tick_near_boundary_end(self, memory_db):
        """Tick at 2026-03-15 09:30:14.999 → bucket 2026-03-15 09:30:00."""
        memory_db.execute("""
            CREATE TABLE test_ticks2 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:14.999' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_bucket_sql("test_ticks2")).fetchone()
        assert row is not None
        bucket_dt = row[0]

        expected = dt(2026, 3, 15, 9, 30, 0)
        assert bucket_dt == expected, f"Expected bucket {expected}, got {bucket_dt}"

    def test_tick_at_next_boundary(self, memory_db):
        """Tick at 2026-03-15 09:30:15.000 → bucket 2026-03-15 09:30:15."""
        memory_db.execute("""
            CREATE TABLE test_ticks3 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:15.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_bucket_sql("test_ticks3")).fetchone()
        assert row is not None
        bucket_dt = row[0]

        expected = dt(2026, 3, 15, 9, 30, 15)
        assert bucket_dt == expected, f"Expected bucket {expected}, got {bucket_dt}"

    def test_tick_before_midnight_boundary(self, memory_db):
        """Tick at 2026-03-15 23:59:59.999 → bucket 2026-03-15 23:59:45."""
        memory_db.execute("""
            CREATE TABLE test_ticks4 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 23:59:59.999' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_bucket_sql("test_ticks4")).fetchone()
        assert row is not None
        bucket_dt = row[0]

        expected = dt(2026, 3, 15, 23, 59, 45)
        assert bucket_dt == expected, f"Expected bucket {expected}, got {bucket_dt}"

    def test_tick_at_midnight(self, memory_db):
        """Tick at 2026-03-16 00:00:00.000 → bucket 2026-03-16 00:00:00."""
        memory_db.execute("""
            CREATE TABLE test_ticks5 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-16 00:00:00.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_bucket_sql("test_ticks5")).fetchone()
        assert row is not None
        bucket_dt = row[0]

        expected = dt(2026, 3, 16, 0, 0, 0)
        assert bucket_dt == expected, f"Expected bucket {expected}, got {bucket_dt}"


class TestOHLCVAggregation:
    """Verify full OHLCV aggregation logic (Spec: Last-Traded / Bid-Ask)."""

    def _assert_float(self, actual, expected: float, name: str):
        """Compare DuckDB result (Decimal) with expected float."""
        assert float(actual) == expected, (
            f"Expected {name} {expected}, got {actual} (type={type(actual).__name__})"
        )

    def test_standard_bucket_with_multiple_ticks(self, memory_db):
        """Multiple ticks in one 15s bucket produce correct OHLCV values."""
        memory_db.execute("""
            CREATE TABLE test_ohlcv1 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:01.000' AS TIMESTAMP),
                 4500.20, 4500.55, 4500.30, 5),
                ('MNQ0626', CAST('2026-03-15 09:30:05.000' AS TIMESTAMP),
                 4500.25, 4500.60, 4500.55, 10),
                ('MNQ0626', CAST('2026-03-15 09:30:10.000' AS TIMESTAMP),
                 4500.15, 4500.50, 4500.25, 8)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        rows = memory_db.execute(_ohlcv_sql("test_ohlcv1")).fetchall()
        assert len(rows) == 1, f"Expected 1 bucket row, got {len(rows)}"

        row = rows[0]
        (
            bucket_dt,
            symbol,
            open_,
            high,
            low,
            close_,
            volume,
            bid_open,
            bid_high,
            bid_low,
            bid_close,
            ask_open,
            ask_high,
            ask_low,
            ask_close,
        ) = row

        expected_dt = dt(2026, 3, 15, 9, 30, 0)
        assert bucket_dt == expected_dt

        # Use float() conversion because DuckDB returns Decimal
        self._assert_float(open_, 4500.30, "open")
        self._assert_float(high, 4500.55, "high")
        self._assert_float(low, 4500.25, "low")
        self._assert_float(close_, 4500.25, "close")
        assert int(volume) == 23, f"Expected volume 23, got {volume}"

        self._assert_float(bid_open, 4500.20, "bid_open")
        self._assert_float(bid_high, 4500.25, "bid_high")
        self._assert_float(bid_low, 4500.15, "bid_low")
        self._assert_float(bid_close, 4500.15, "bid_close")

        self._assert_float(ask_open, 4500.55, "ask_open")
        self._assert_float(ask_high, 4500.60, "ask_high")
        self._assert_float(ask_low, 4500.50, "ask_low")
        self._assert_float(ask_close, 4500.50, "ask_close")

    def test_single_tick_bucket(self, memory_db):
        """Single-tick bucket: open=high=low=close=last, volume=tick volume."""
        memory_db.execute("""
            CREATE TABLE test_ohlcv2 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:01.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.35, 5)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        rows = memory_db.execute(_ohlcv_sql("test_ohlcv2")).fetchall()
        assert len(rows) == 1, f"Expected 1 bucket row, got {len(rows)}"

        row = rows[0]
        (_dt, _sym, open_, high, low, close_, volume, _, _, _, _, _, _, _, _) = row

        open_f = float(open_)
        assert open_f == float(high) == float(low) == float(close_) == 4500.35, (
            f"Single-tick OHLC should all be same: {open_}/{high}/{low}/{close_}"
        )
        assert int(volume) == 5, f"Expected volume 5, got {volume}"

    def test_multiple_symbols_separate_buckets(self, memory_db):
        """Different symbols in same 15s window produce separate buckets."""
        memory_db.execute("""
            CREATE TABLE test_ohlcv3 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:01.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.35, 5),
                ('ESU0626', CAST('2026-03-15 09:30:05.000' AS TIMESTAMP),
                 5000.00, 5001.00, 5000.50, 10)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        rows = memory_db.execute(_ohlcv_sql("test_ohlcv3")).fetchall()
        assert len(rows) == 2, f"Expected 2 bucket rows, got {len(rows)}"

        symbols = {r[1] for r in rows}
        assert symbols == {"MNQ0626", "ESU0626"}

    def test_null_bid_ask_in_middle_tick(self, memory_db):
        """Null bid/ask on middle tick; first and last have non-null.

        bid_open/close from first/last non-null ticks; min/max ignore NULLs.
        """
        memory_db.execute("""
            CREATE TABLE test_ohlcv4 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:01.000' AS TIMESTAMP),
                 4500.20, 4500.55, 4500.30, 5),
                ('MNQ0626', CAST('2026-03-15 09:30:05.000' AS TIMESTAMP),
                 NULL, NULL, 4500.35, 10),
                ('MNQ0626', CAST('2026-03-15 09:30:10.000' AS TIMESTAMP),
                 4500.25, 4500.60, 4500.40, 8)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        rows = memory_db.execute(_ohlcv_sql("test_ohlcv4")).fetchall()
        assert len(rows) == 1

        row = rows[0]
        (
            _,
            _,
            _,
            _,
            _,
            _,
            _,
            bid_open,
            bid_high,
            bid_low,
            bid_close,
            ask_open,
            ask_high,
            ask_low,
            ask_close,
        ) = row

        # First tick bid=4500.20, last tick bid=4500.25; middle is NULL
        self._assert_float(bid_open, 4500.20, "bid_open (first non-null)")
        self._assert_float(bid_high, 4500.25, "bid_high (max of non-null)")
        self._assert_float(bid_low, 4500.20, "bid_low (min of non-null)")
        self._assert_float(bid_close, 4500.25, "bid_close (last non-null)")
        # First tick ask=4500.55, last tick ask=4500.60; middle is NULL
        self._assert_float(ask_open, 4500.55, "ask_open (first non-null)")
        self._assert_float(ask_high, 4500.60, "ask_high (max of non-null)")
        self._assert_float(ask_low, 4500.55, "ask_low (min of non-null)")
        self._assert_float(ask_close, 4500.60, "ask_close (last non-null)")

    def test_microsecond_precision_no_fractional_seconds(self, memory_db):
        """Bucket datetime has second precision — no fractional seconds."""
        memory_db.execute("""
            CREATE TABLE test_ohlcv5 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:01.123456' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.35, 1)
            ) t(symbol, event_ts, bid, ask, last, volume)
        """)

        row = memory_db.execute(_bucket_sql("test_ohlcv5")).fetchone()
        assert row is not None
        bucket_dt = row[0]

        assert bucket_dt.microsecond == 0, (
            f"Bucket datetime should have 0 microseconds, got {bucket_dt.microsecond}"
        )
        expected = dt(2026, 3, 15, 9, 30, 0)
        assert bucket_dt == expected


# ---------------------------------------------------------------------------
# Multi-Timeframe Bucket Alignment
# Spec: Multi-Timeframe OHLCV — bucket formulas for 1m/5m/1h/1d
# Formula (non-daily): date_trunc('second', event_ts) - INTERVAL
#   (EXTRACT(SECOND FROM event_ts) % bucket_seconds) SECOND
# Formula (daily): date_trunc('day', event_ts)
# ---------------------------------------------------------------------------


def _bucket_sql_for_granularity(
    bucket_seconds: int, source_table: str = "test_ticks", is_daily: bool = False
) -> str:
    """Return bucket alignment SQL matching the ohlcv_aggregate macro for a given bucket size.

    For daily: date_trunc('day', event_ts)
    For non-daily: epoch-second integer division truncates to bucket boundary.
    """
    if is_daily:
        bucket_expr = "date_trunc('day', datetime) AS datetime"
    else:
        # Universal formula: epoch-second truncation via FLOOR to handle any bucket size
        bucket_expr = (
            f"CAST(TIMESTAMP 'epoch' + CAST(FLOOR(EXTRACT(epoch FROM datetime)"
            f" / {bucket_seconds}) * {bucket_seconds} AS BIGINT)"
            f" * INTERVAL '1 second' AS TIMESTAMP) AS datetime"
        )
    return f"""
        SELECT
            {bucket_expr},
            symbol, last, bid, ask, volume
        FROM {source_table}
    """


def _ohlcv_sql_for_granularity(
    bucket_seconds: int, source_table: str = "test_ticks", is_daily: bool = False
) -> str:
    """Return full OHLCV aggregation SQL matching the ohlcv_aggregate macro (OHLCV src)."""
    if is_daily:
        bucket_expr = "date_trunc('day', datetime)"
    else:
        bucket_expr = (
            f"CAST(TIMESTAMP 'epoch' + CAST(FLOOR(EXTRACT(epoch FROM datetime)"
            f" / {bucket_seconds}) * {bucket_seconds} AS BIGINT)"
            " * INTERVAL '1 second' AS TIMESTAMP)"
        )
    return f"""
        WITH bucketed AS (
            SELECT
                {bucket_expr} AS bucket_dt,
                symbol, open, high, low, close, volume,
                bid_open, bid_high, bid_low, bid_close,
                ask_open, ask_high, ask_low, ask_close,
                datetime AS src_dt,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol, {bucket_expr}
                    ORDER BY datetime
                ) AS rn_asc,
                ROW_NUMBER() OVER (
                    PARTITION BY symbol, {bucket_expr}
                    ORDER BY datetime DESC
                ) AS rn_desc
            FROM {source_table}
        )
        SELECT
            bucket_dt AS datetime,
            symbol,
            MAX(CASE WHEN rn_asc = 1 THEN open END) AS open,
            MAX(high) AS high,
            MIN(low) AS low,
            MAX(CASE WHEN rn_desc = 1 THEN close END) AS close,
            SUM(volume) AS volume,
            MAX(CASE WHEN rn_asc = 1 THEN bid_open END) AS bid_open,
            MAX(bid_high) AS bid_high,
            MIN(bid_low) AS bid_low,
            MAX(CASE WHEN rn_desc = 1 THEN bid_close END) AS bid_close,
            MAX(CASE WHEN rn_asc = 1 THEN ask_open END) AS ask_open,
            MAX(ask_high) AS ask_high,
            MIN(ask_low) AS ask_low,
            MAX(CASE WHEN rn_desc = 1 THEN ask_close END) AS ask_close
        FROM bucketed
        GROUP BY bucket_dt, symbol
    """


class TestMultiTimeframeBucketAlignment:
    """Verify bucket alignment formulas for multiple timeframes."""

    def test_1m_tick_at_exact_boundary(self, memory_db):
        """1m: Tick at 09:30:00 → bucket 09:30:00."""
        memory_db.execute("""
            CREATE TABLE test_mtf1 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:00.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, datetime, bid, ask, last, volume)
        """)
        row = memory_db.execute(_bucket_sql_for_granularity(60, "test_mtf1")).fetchone()
        assert row is not None
        assert row[0] == dt(2026, 3, 15, 9, 30, 0)

    def test_1m_tick_at_59s(self, memory_db):
        """1m: Tick at 09:30:59 → bucket 09:30:00."""
        memory_db.execute("""
            CREATE TABLE test_mtf2 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:59.999' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, datetime, bid, ask, last, volume)
        """)
        row = memory_db.execute(_bucket_sql_for_granularity(60, "test_mtf2")).fetchone()
        assert row is not None
        assert row[0] == dt(2026, 3, 15, 9, 30, 0)

    def test_1m_tick_at_next_minute(self, memory_db):
        """1m: Tick at 09:31:00 → bucket 09:31:00."""
        memory_db.execute("""
            CREATE TABLE test_mtf3 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:31:00.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, datetime, bid, ask, last, volume)
        """)
        row = memory_db.execute(_bucket_sql_for_granularity(60, "test_mtf3")).fetchone()
        assert row is not None
        assert row[0] == dt(2026, 3, 15, 9, 31, 0)

    def test_5m_alignment(self, memory_db):
        """5m: Tick at 09:33:00 → bucket 09:30:00."""
        memory_db.execute("""
            CREATE TABLE test_mtf4 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:33:00.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, datetime, bid, ask, last, volume)
        """)
        row = memory_db.execute(_bucket_sql_for_granularity(300, "test_mtf4")).fetchone()
        assert row is not None
        assert row[0] == dt(2026, 3, 15, 9, 30, 0), "5m: 09:33:00 → 09:30:00"

    def test_1h_alignment_second_hour(self, memory_db):
        """1h: Tick at 10:15:00 → bucket 10:00:00."""
        memory_db.execute("""
            CREATE TABLE test_mtf5 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 10:15:00.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, datetime, bid, ask, last, volume)
        """)
        row = memory_db.execute(_bucket_sql_for_granularity(3600, "test_mtf5")).fetchone()
        assert row is not None
        assert row[0] == dt(2026, 3, 15, 10, 0, 0), "1h: 10:15:00 → 10:00:00"

    def test_1h_alignment_exact_hour(self, memory_db):
        """1h: Tick at 11:00:00 → bucket 11:00:00."""
        memory_db.execute("""
            CREATE TABLE test_mtf6 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 11:00:00.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, datetime, bid, ask, last, volume)
        """)
        row = memory_db.execute(_bucket_sql_for_granularity(3600, "test_mtf6")).fetchone()
        assert row is not None
        assert row[0] == dt(2026, 3, 15, 11, 0, 0), "1h: 11:00:00 → 11:00:00"

    def test_daily_alignment(self, memory_db):
        """1d: date_trunc('day', datetime) → 2026-03-15 00:00:00."""
        memory_db.execute("""
            CREATE TABLE test_mtf7 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 14:30:00.000' AS TIMESTAMP),
                 4500.25, 4500.50, 4500.50, 1)
            ) t(symbol, datetime, bid, ask, last, volume)
        """)
        row = memory_db.execute(
            _bucket_sql_for_granularity(86400, "test_mtf7", is_daily=True)
        ).fetchone()
        assert row is not None
        assert row[0] == dt(2026, 3, 15, 0, 0, 0), "1d: any time → midnight"


class TestMultiTimeframeAggregation:
    """Verify full OHLCV aggregation for multi-timeframe buckets."""

    def _assert_float(self, actual, expected: float, name: str):
        assert float(actual) == expected, (
            f"Expected {name} {expected}, got {actual} (type={type(actual).__name__})"
        )

    def test_1m_aggregation_multiple_buckets(self, memory_db):
        """1m: Multi-Tick 15s bars spanning 2 minutes produce 2 buckets with correct OHLCV."""
        memory_db.execute("""
            CREATE TABLE test_mtf_agg1 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:00.000' AS TIMESTAMP),
                 4500.20, 4500.75, 4500.20, 4500.55, 5,
                 4500.20, 4500.70, 4500.20, 4500.55, 4500.25, 4500.80, 4500.25, 4500.60),
                ('MNQ0626', CAST('2026-03-15 09:30:30.000' AS TIMESTAMP),
                 4500.55, 4500.80, 4500.30, 4500.65, 10,
                 4500.55, 4500.75, 4500.30, 4500.60, 4500.60, 4500.85, 4500.35, 4500.70),
                ('MNQ0626', CAST('2026-03-15 09:31:00.000' AS TIMESTAMP),
                 4500.25, 4500.60, 4500.20, 4500.50, 8,
                 4500.25, 4500.55, 4500.20, 4500.45, 4500.30, 4500.65, 4500.25, 4500.55)
            ) t(symbol, datetime, open, high, low, close, volume,
                bid_open, bid_high, bid_low, bid_close,
                ask_open, ask_high, ask_low, ask_close)
        """)
        rows = memory_db.execute(_ohlcv_sql_for_granularity(60, "test_mtf_agg1")).fetchall()
        assert len(rows) == 2, f"Expected 2 one-minute buckets, got {len(rows)}"

        # Check the two buckets
        buckets = {r[0]: r for r in rows}
        assert dt(2026, 3, 15, 9, 30, 0) in buckets, "Missing 09:30 bucket"
        assert dt(2026, 3, 15, 9, 31, 0) in buckets, "Missing 09:31 bucket"

        b1 = buckets[dt(2026, 3, 15, 9, 30, 0)]
        self._assert_float(b1[2], 4500.20, "09:30 open")  # first 15s bar: open=4500.20
        self._assert_float(b1[3], 4500.80, "09:30 high")  # max(high): 4500.80 (bar 2)
        self._assert_float(b1[4], 4500.20, "09:30 low")  # min(low): 4500.20
        self._assert_float(b1[5], 4500.65, "09:30 close")  # last close: 4500.65
        assert int(b1[6]) == 15, "09:30 volume (5+10)"
        # Bid/ask checks
        self._assert_float(b1[7], 4500.20, "09:30 bid_open")
        self._assert_float(b1[8], 4500.75, "09:30 bid_high")
        self._assert_float(b1[10], 4500.60, "09:30 bid_close")
        self._assert_float(b1[11], 4500.25, "09:30 ask_open")
        self._assert_float(b1[12], 4500.85, "09:30 ask_high")
        self._assert_float(b1[14], 4500.70, "09:30 ask_close")

        b2 = buckets[dt(2026, 3, 15, 9, 31, 0)]
        self._assert_float(b2[2], 4500.25, "09:31 open")  # first bar open: 4500.25
        self._assert_float(b2[5], 4500.50, "09:31 close")  # last close: 4500.50
        assert int(b2[6]) == 8, "09:31 volume"

    def test_1h_aggregation(self, memory_db):
        """1h: 15s OHLCV bars spanning 2 hours produce 2 hourly buckets."""
        memory_db.execute("""
            CREATE TABLE test_mtf_agg2 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:00.000' AS TIMESTAMP),
                 4500.20, 4500.55, 4500.10, 4500.30, 5,
                 4500.15, 4500.50, 4500.05, 4500.25, 4500.25, 4500.60, 4500.15, 4500.35),
                ('MNQ0626', CAST('2026-03-15 09:45:00.000' AS TIMESTAMP),
                 4500.30, 4500.65, 4500.20, 4500.55, 10,
                 4500.25, 4500.60, 4500.15, 4500.50, 4500.35, 4500.70, 4500.25, 4500.60),
                ('MNQ0626', CAST('2026-03-15 10:15:00.000' AS TIMESTAMP),
                 4500.40, 4500.75, 4500.30, 4500.65, 8,
                 4500.35, 4500.70, 4500.25, 4500.60, 4500.45, 4500.80, 4500.35, 4500.70)
            ) t(symbol, datetime, open, high, low, close, volume,
                bid_open, bid_high, bid_low, bid_close,
                ask_open, ask_high, ask_low, ask_close)
        """)
        rows = memory_db.execute(_ohlcv_sql_for_granularity(3600, "test_mtf_agg2")).fetchall()
        assert len(rows) == 2, f"Expected 2 hourly buckets, got {len(rows)}"

    def test_daily_aggregation(self, memory_db):
        """1d: date_trunc('day') groups all OHLCV bars into daily buckets."""
        memory_db.execute("""
            CREATE TABLE test_mtf_agg3 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:00.000' AS TIMESTAMP),
                 4500.20, 4500.75, 4500.10, 4500.55, 5,
                 4500.15, 4500.70, 4500.05, 4500.50, 4500.25, 4500.80, 4500.15, 4500.60),
                ('MNQ0626', CAST('2026-03-15 14:30:00.000' AS TIMESTAMP),
                 4500.55, 4500.85, 4500.30, 4500.70, 10,
                 4500.50, 4500.80, 4500.25, 4500.65, 4500.60, 4500.90, 4500.35, 4500.75),
                ('MNQ0626', CAST('2026-03-16 09:30:00.000' AS TIMESTAMP),
                 4500.30, 4500.65, 4500.20, 4500.50, 8,
                 4500.25, 4500.60, 4500.15, 4500.45, 4500.35, 4500.70, 4500.25, 4500.55)
            ) t(symbol, datetime, open, high, low, close, volume,
                bid_open, bid_high, bid_low, bid_close,
                ask_open, ask_high, ask_low, ask_close)
        """)
        rows = memory_db.execute(
            _ohlcv_sql_for_granularity(86400, "test_mtf_agg3", is_daily=True)
        ).fetchall()
        assert len(rows) == 2, f"Expected 2 daily buckets, got {len(rows)}"

        buckets = {r[0]: r for r in rows}
        assert dt(2026, 3, 15, 0, 0, 0) in buckets, "Missing Mar 15 bucket"
        assert dt(2026, 3, 16, 0, 0, 0) in buckets, "Missing Mar 16 bucket"

        mar15 = buckets[dt(2026, 3, 15, 0, 0, 0)]
        self._assert_float(mar15[2], 4500.20, "Mar 15 open")  # first bar open=4500.20
        self._assert_float(mar15[3], 4500.85, "Mar 15 high")  # max high=4500.85 (bar 2)
        self._assert_float(mar15[4], 4500.10, "Mar 15 low")  # min low=4500.10 (bar 1)
        self._assert_float(mar15[5], 4500.70, "Mar 15 close")  # last bar close=4500.70
        assert int(mar15[6]) == 15, "Mar 15 volume (5+10)"

    def test_ohlcv_output_has_all_15_columns(self, memory_db):
        """Multi-timeframe aggregation produces all 15 OHLCV columns from OHLCV source."""
        memory_db.execute("""
            CREATE TABLE test_mtf_agg4 AS
            SELECT * FROM (VALUES
                ('MNQ0626', CAST('2026-03-15 09:30:00.000' AS TIMESTAMP),
                 4500.20, 4500.55, 4500.10, 4500.30, 5,
                 4500.15, 4500.50, 4500.05, 4500.25, 4500.25, 4500.60, 4500.15, 4500.35)
            ) t(symbol, datetime, open, high, low, close, volume,
                bid_open, bid_high, bid_low, bid_close,
                ask_open, ask_high, ask_low, ask_close)
        """)
        row = memory_db.execute(_ohlcv_sql_for_granularity(3600, "test_mtf_agg4")).fetchone()
        assert row is not None
        # 15 columns: datetime, symbol, open, high, low, close, volume,
        #             bid_open, bid_high, bid_low, bid_close,
        #             ask_open, ask_high, ask_low, ask_close
        assert len(row) == 15, f"Expected 15 columns, got {len(row)}"


# ---------------------------------------------------------------------------
# OHLCVBar Pydantic Schema
# Spec: Requirement "API Response Schema"
# ---------------------------------------------------------------------------


class TestOHLCVBarSchema:
    """Verify OHLCVBar Pydantic model serialization and validation."""

    def test_full_response_shape(self):
        """All 15 fields serialize correctly with correct types."""
        bar = OHLCVBar(
            datetime=dt(2026, 3, 15, 9, 30, 0),
            symbol="MNQ0626",
            open=4500.25,
            high=4500.75,
            low=4500.00,
            close=4500.50,
            volume=100,
            bid_open=4500.20,
            bid_high=4500.70,
            bid_low=4499.95,
            bid_close=4500.45,
            ask_open=4500.30,
            ask_high=4500.80,
            ask_low=4500.05,
            ask_close=4500.55,
        )

        data = bar.model_dump(mode="json")
        assert data["datetime"] == "2026-03-15T09:30:00"
        assert data["symbol"] == "MNQ0626"
        assert data["open"] == 4500.25
        assert data["high"] == 4500.75
        assert data["low"] == 4500.00
        assert data["close"] == 4500.50
        assert data["volume"] == 100
        assert data["bid_open"] == 4500.20
        assert data["bid_high"] == 4500.70
        assert data["bid_low"] == 4499.95
        assert data["bid_close"] == 4500.45
        assert data["ask_open"] == 4500.30
        assert data["ask_high"] == 4500.80
        assert data["ask_low"] == 4500.05
        assert data["ask_close"] == 4500.55

    def test_json_round_trip(self):
        """Serialize to JSON and back produces same values."""
        bar = OHLCVBar(
            datetime=dt(2026, 3, 15, 9, 30, 0),
            symbol="MNQ0626",
            open=4500.25,
            high=4500.75,
            low=4500.00,
            close=4500.50,
            volume=100,
            bid_open=4500.20,
            bid_high=4500.70,
            bid_low=4499.95,
            bid_close=4500.45,
            ask_open=4500.30,
            ask_high=4500.80,
            ask_low=4500.05,
            ask_close=4500.55,
        )

        json_str = bar.model_dump_json()
        bar2 = OHLCVBar.model_validate_json(json_str)

        assert bar2.datetime == bar.datetime
        assert bar2.symbol == bar.symbol
        assert bar2.open == bar.open
        assert bar2.high == bar.high
        assert bar2.low == bar.low
        assert bar2.close == bar.close
        assert bar2.volume == bar.volume
        assert bar2.bid_open == bar.bid_open
        assert bar2.ask_close == bar.ask_close

    def test_from_orm_compatible(self):
        """OHLCVBar can be created from a dict (from_attributes compatible)."""
        data = {
            "datetime": dt(2026, 3, 15, 9, 30, 0),
            "symbol": "MNQ0626",
            "open": 4500.25,
            "high": 4500.75,
            "low": 4500.00,
            "close": 4500.50,
            "volume": 100,
            "bid_open": 4500.20,
            "bid_high": 4500.70,
            "bid_low": 4499.95,
            "bid_close": 4500.45,
            "ask_open": 4500.30,
            "ask_high": 4500.80,
            "ask_low": 4500.05,
            "ask_close": 4500.55,
        }
        bar = OHLCVBar.model_validate(data)
        assert bar.symbol == "MNQ0626"
        assert bar.volume == 100

    def test_missing_required_field_raises(self):
        """Missing 'symbol' field raises ValidationError."""
        data = {
            "datetime": dt(2026, 3, 15, 9, 30, 0),
            "open": 4500.25,
            "high": 4500.75,
            "low": 4500.00,
            "close": 4500.50,
            "volume": 100,
            "bid_open": 4500.20,
            "bid_high": 4500.70,
            "bid_low": 4499.95,
            "bid_close": 4500.45,
            "ask_open": 4500.30,
            "ask_high": 4500.80,
            "ask_low": 4500.05,
            "ask_close": 4500.55,
        }
        with pytest.raises(ValidationError):
            OHLCVBar.model_validate(data)

    def test_volume_as_int(self):
        """Volume field accepts int values."""
        bar = OHLCVBar(
            datetime=dt(2026, 3, 15, 9, 30, 0),
            symbol="MNQ0626",
            open=1.0,
            high=2.0,
            low=1.0,
            close=2.0,
            volume=999999999,
            bid_open=1.0,
            bid_high=2.0,
            bid_low=1.0,
            bid_close=2.0,
            ask_open=1.0,
            ask_high=2.0,
            ask_low=1.0,
            ask_close=2.0,
        )
        assert bar.volume == 999999999
        assert isinstance(bar.volume, int)


# ---------------------------------------------------------------------------
# API Integration Test
# Spec: Requirement "API Query by Symbol"
# ---------------------------------------------------------------------------


class TestOHLCVApiEndpoint:
    """Integration tests for GET /api/v1/ohlcv."""

    @pytest.mark.asyncio
    async def test_missing_symbol_returns_422(self, ohlcv_client):
        """GET /api/v1/ohlcv without symbol returns 422."""
        response = await ohlcv_client.get("/api/v1/ohlcv")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_empty_result_for_unknown_symbol(self, ohlcv_client):
        """Known symbol with no bars returns empty array."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=UNKNOWN")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_valid_query_returns_bars(self, ohlcv_client):
        """Valid symbol query returns list of OHLCVBar objects with all 15 fields."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Expected at least 1 bar for MNQ0626"

        bar = data[0]
        assert "datetime" in bar
        assert "symbol" in bar
        assert "open" in bar
        assert "high" in bar
        assert "low" in bar
        assert "close" in bar
        assert "volume" in bar
        assert "bid_open" in bar
        assert "bid_high" in bar
        assert "bid_low" in bar
        assert "bid_close" in bar
        assert "ask_open" in bar
        assert "ask_high" in bar
        assert "ask_low" in bar
        assert "ask_close" in bar
        assert isinstance(bar["datetime"], str)
        assert isinstance(bar["symbol"], str)
        assert isinstance(bar["volume"], int)

    @pytest.mark.asyncio
    async def test_date_filtered_query(self, ohlcv_client):
        """start_date and end_date parameters filter correctly."""
        response = await ohlcv_client.get(
            "/api/v1/ohlcv?symbol=MNQ0626&start_date=2026-03-15&end_date=2026-03-16"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for bar in data:
            bar_dt = dt.fromisoformat(bar["datetime"])
            assert bar_dt >= dt(2026, 3, 15)
            assert bar_dt < dt(2026, 3, 16)

    @pytest.mark.asyncio
    async def test_results_ordered_by_datetime(self, ohlcv_client):
        """Results sorted by datetime ascending."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 1, "Need at least 2 bars to test ordering"

        timestamps = [dt.fromisoformat(bar["datetime"]) for bar in data]
        assert timestamps == sorted(timestamps), "Results must be sorted by datetime ascending"

    @pytest.mark.asyncio
    async def test_date_filtered_limits_results(self, ohlcv_client):
        """Query with date range returns subset of full results."""
        full = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626")
        filtered = await ohlcv_client.get(
            "/api/v1/ohlcv?symbol=MNQ0626&start_date=2026-03-15&end_date=2026-03-15"
        )
        assert filtered.status_code == 200
        full_data = full.json()
        filtered_data = filtered.json()
        assert len(filtered_data) <= len(full_data)

    @pytest.mark.asyncio
    async def test_symbol_filter_returns_only_requested(self, ohlcv_client):
        """Query for one symbol does not return results for others."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        symbols = {bar["symbol"] for bar in data}
        assert symbols == {"MNQ0626"}, f"Expected only MNQ0626, got {symbols}"


# ---------------------------------------------------------------------------
# Multi-Granularity API Tests
# Spec: API Granularity Parameter — GET /api/v1/ohlcv?symbol=X&granularity=1m
# ---------------------------------------------------------------------------


class TestMultiGranularity:
    """Integration tests for the granularity parameter on GET /api/v1/ohlcv."""

    @pytest.mark.asyncio
    async def test_backward_compat_no_granularity(self, ohlcv_client):
        """No granularity param defaults to 15s and returns identical results to current."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        # Verify all 15 fields present
        bar = data[0]
        assert "datetime" in bar
        assert "open" in bar
        assert "high" in bar
        assert "low" in bar
        assert "close" in bar
        assert "volume" in bar
        assert "bid_open" in bar
        assert "bid_close" in bar
        assert "ask_open" in bar
        assert "ask_close" in bar

    @pytest.mark.asyncio
    async def test_granularity_1m_returns_bars(self, ohlcv_client):
        """Valid granularity=1m returns list of bars with all 15 fields."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626&granularity=1m")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Expected at least 1 bar for MNQ0626 at 1m"
        bar = data[0]
        assert "datetime" in bar
        assert "symbol" in bar
        assert "open" in bar
        assert "high" in bar
        assert "low" in bar
        assert "close" in bar
        assert "volume" in bar

    @pytest.mark.asyncio
    async def test_granularity_1d_returns_bars(self, ohlcv_client):
        """Valid granularity=1d returns daily bars."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626&granularity=1d")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "Expected at least 1 daily bar for MNQ0626"

    @pytest.mark.asyncio
    async def test_invalid_granularity_returns_422(self, ohlcv_client):
        """Invalid granularity value returns 422."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626&granularity=invalid")
        assert response.status_code == 422, (
            f"Expected 422, got {response.status_code}: {response.text}"
        )

    @pytest.mark.asyncio
    async def test_granularity_missing_symbol_returns_empty(self, ohlcv_client):
        """Valid granularity with unknown symbol returns empty array."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=UNKNOWN&granularity=1m")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_granularity_1h_returns_bars(self, ohlcv_client):
        """Valid granularity=1h returns hourly bars."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626&granularity=1h")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_granularity_5m_returns_bars(self, ohlcv_client):
        """Valid granularity=5m returns 5-minute bars."""
        response = await ohlcv_client.get("/api/v1/ohlcv?symbol=MNQ0626&granularity=5m")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    @pytest.mark.asyncio
    async def test_date_filtered_with_granularity(self, ohlcv_client):
        """start_date and end_date work with granularity parameter."""
        response = await ohlcv_client.get(
            "/api/v1/ohlcv?symbol=MNQ0626&granularity=1m&start_date=2026-03-15&end_date=2026-03-16"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for bar in data:
            bar_dt = dt.fromisoformat(bar["datetime"])
            assert bar_dt >= dt(2026, 3, 15)
            assert bar_dt < dt(2026, 3, 16)
