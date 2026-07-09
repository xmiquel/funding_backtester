"""Tests for the vectorbt-compatible indicator feature loader."""
from __future__ import annotations

import pathlib

import duckdb
import pandas as pd
import pytest

from funding_backtester.indicators.vectorbt_loader import load_features


def _seed_ohlcv_and_stage(conn: duckdb.DuckDBPyConnection) -> None:
    """Seed an OHLCV source table and indicator_feature_stage with test data."""
    conn.execute(
        """
        CREATE TABLE ohlcv_15s (
            datetime TIMESTAMP NOT NULL,
            symbol VARCHAR NOT NULL,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT
        )
        """
    )
    conn.execute(
        """
        INSERT INTO ohlcv_15s VALUES
        ('2024-01-03 09:30:00', 'ES', 4500.0, 4501.0, 4499.0, 4500.5, 100),
        ('2024-01-03 09:30:15', 'ES', 4500.5, 4502.0, 4500.0, 4501.0, 150)
        """
    )

    conn.execute(
        """
        CREATE TABLE indicator_feature_stage (
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
    conn.execute(
        """
        INSERT INTO indicator_feature_stage VALUES
        ('2024-01-03 09:30:00', 'ES', '15s', 'ohlcv_15s',
         'sma', 'fid_sma_es', 'phash_sma20', '{"length":20}', 'sma', 4500.5,
         '2024-01-03 09:30:00', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true),
        ('2024-01-03 09:30:15', 'ES', '15s', 'ohlcv_15s',
         'sma', 'fid_sma_es', 'phash_sma20', '{"length":20}', 'sma', 4501.0,
         '2024-01-03 09:30:15', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true),
        ('2024-01-03 09:30:00', 'ES', '15s', 'ohlcv_15s',
         'rsi', 'fid_rsi_es', 'phash_rsi14', '{"length":14}', 'rsi', 55.5,
         '2024-01-03 09:30:00', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true),
        ('2024-01-03 09:30:15', 'ES', '15s', 'ohlcv_15s',
         'rsi', 'fid_rsi_es', 'phash_rsi14', '{"length":14}', 'rsi', 60.2,
         '2024-01-03 09:30:15', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true),
        ('2024-01-03 10:00:00', 'NQ', '15s', 'ohlcv_15s',
         'sma', 'fid_sma_nq', 'phash_sma20', '{"length":20}', 'sma', 15000.0,
         '2024-01-03 10:00:00', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true)
        """
    )


class TestLoadFeatures:
    """Test the ``load_features`` vectorbt-compatible loader."""

    def test_returns_close_and_feature_dataframe(self, tmp_path: pathlib.Path) -> None:
        """``load_features`` returns (close Series, features DataFrame) tuple."""
        db_path = tmp_path / "test.duckdb"
        conn = duckdb.connect(str(db_path))
        _seed_ohlcv_and_stage(conn)
        conn.close()

        close, features = load_features(
            database_path=db_path,
            symbol="ES",
            timeframe="15s",
            source_model="ohlcv_15s",
        )

        assert isinstance(close, pd.Series)
        assert close.name == "close"
        assert len(close) == 2
        assert close.iloc[0] == 4500.5
        assert close.iloc[-1] == 4501.0

        assert isinstance(features, pd.DataFrame)
        assert len(features) == 2
        assert len(features.columns) == 2  # sma_sma + rsi_rsi (one output per indicator)
        assert "sma_sma_phash_sma20" in features.columns
        assert "rsi_rsi_phash_rsi14" in features.columns
        assert features.loc[features.index[0], "sma_sma_phash_sma20"] == 4500.5
        assert features.loc[features.index[-1], "rsi_rsi_phash_rsi14"] == 60.2

    def test_returns_different_symbol_not_interleaved(self, tmp_path: pathlib.Path) -> None:
        """``load_features`` with NQ returns that symbol's features only, not ES."""
        db_path = tmp_path / "test_nq.duckdb"
        conn = duckdb.connect(str(db_path))
        _seed_ohlcv_and_stage(conn)
        conn.close()

        close, features = load_features(
            database_path=db_path,
            symbol="ES",
            timeframe="15s",
            source_model="ohlcv_15s",
            feature_names=("sma",),
        )

        assert len(close) == 2
        assert len(features) == 2
        assert list(features.columns) == ["sma_sma_phash_sma20"]

    def test_columns_include_parameter_hash(self, tmp_path: pathlib.Path) -> None:
        """Feature columns include parameter_hash for disambiguation."""
        db_path = tmp_path / "test_hash.duckdb"
        conn = duckdb.connect(str(db_path))
        _seed_ohlcv_and_stage(conn)
        conn.close()

        _, features = load_features(
            database_path=db_path,
            symbol="ES",
            timeframe="15s",
            source_model="ohlcv_15s",
        )

        for col in features.columns:
            parts = col.split("_")
            assert len(parts) >= 3  # feature_output_hash

    def test_returns_empty_on_no_matching_data(self, tmp_path: pathlib.Path) -> None:
        """Non-existent symbol returns empty Series and DataFrame."""
        db_path = tmp_path / "test_empty.duckdb"
        conn = duckdb.connect(str(db_path))
        _seed_ohlcv_and_stage(conn)
        conn.close()

        close, features = load_features(
            database_path=db_path,
            symbol="NONEXISTENT",
            timeframe="15s",
            source_model="ohlcv_15s",
        )

        assert isinstance(close, pd.Series)
        assert close.empty
        assert isinstance(features, pd.DataFrame)
        assert features.empty

    def test_feature_names_filter_returns_subset(self, tmp_path: pathlib.Path) -> None:
        """Filtering by feature_names returns only requested features."""
        db_path = tmp_path / "test_filter.duckdb"
        conn = duckdb.connect(str(db_path))
        _seed_ohlcv_and_stage(conn)
        conn.close()

        _, features = load_features(
            database_path=db_path,
            symbol="ES",
            timeframe="15s",
            source_model="ohlcv_15s",
            feature_names=("sma",),
        )

        assert list(features.columns) == ["sma_sma_phash_sma20"]
        assert len(features) == 2

    def test_datetime_index_is_sorted(self, tmp_path: pathlib.Path) -> None:
        """Returned DataFrames have a monotonically increasing DatetimeIndex."""
        db_path = tmp_path / "test_sort.duckdb"
        conn = duckdb.connect(str(db_path))
        _seed_ohlcv_and_stage(conn)
        conn.close()

        close, features = load_features(
            database_path=db_path,
            symbol="ES",
            timeframe="15s",
            source_model="ohlcv_15s",
        )

        assert close.index.is_monotonic_increasing
        assert features.index.is_monotonic_increasing

    def test_multi_output_indicator_creates_separate_columns(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Multi-output indicator (MACD) creates separate columns per output."""
        db_path = tmp_path / "test_multi.duckdb"
        conn = duckdb.connect(str(db_path))
        _seed_ohlcv_and_stage(conn)
        conn.execute(
            """
            INSERT INTO indicator_feature_stage VALUES
            ('2024-01-03 09:30:00', 'ES', '15s', 'ohlcv_15s',
             'macd', 'fid_macd_es', 'phash_macd',
             '{"fastperiod":12,"slowperiod":26,"signalperiod":9}',
             'macd', 10.5,
             '2024-01-03 09:30:00', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true),
            ('2024-01-03 09:30:00', 'ES', '15s', 'ohlcv_15s',
             'macd', 'fid_macd_es', 'phash_macd',
             '{"fastperiod":12,"slowperiod":26,"signalperiod":9}',
             'macd_signal', 9.8,
             '2024-01-03 09:30:00', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true),
            ('2024-01-03 09:30:00', 'ES', '15s', 'ohlcv_15s',
             'macd', 'fid_macd_es', 'phash_macd',
             '{"fastperiod":12,"slowperiod":26,"signalperiod":9}',
             'macd_hist', 0.7,
             '2024-01-03 09:30:00', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true),
            ('2024-01-03 09:30:15', 'ES', '15s', 'ohlcv_15s',
             'macd', 'fid_macd_es', 'phash_macd',
             '{"fastperiod":12,"slowperiod":26,"signalperiod":9}',
             'macd', 11.0,
             '2024-01-03 09:30:15', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true),
            ('2024-01-03 09:30:15', 'ES', '15s', 'ohlcv_15s',
             'macd', 'fid_macd_es', 'phash_macd',
             '{"fastperiod":12,"slowperiod":26,"signalperiod":9}',
             'macd_signal', 10.1,
             '2024-01-03 09:30:15', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true),
            ('2024-01-03 09:30:15', 'ES', '15s', 'ohlcv_15s',
             'macd', 'fid_macd_es', 'phash_macd',
             '{"fastperiod":12,"slowperiod":26,"signalperiod":9}',
             'macd_hist', 0.9,
             '2024-01-03 09:30:15', 'indicator-layer-v1', '1.0.17', true, '0.6.8', true)
            """
        )
        conn.close()

        _, features = load_features(
            database_path=db_path,
            symbol="ES",
            timeframe="15s",
            source_model="ohlcv_15s",
            feature_names=("sma", "macd"),
        )

        assert "macd_macd_phash_macd" in features.columns
        assert "macd_macd_signal_phash_macd" in features.columns
        assert "macd_macd_hist_phash_macd" in features.columns
        assert len(features) == 2
        assert features.loc[features.index[0], "macd_macd_phash_macd"] == 10.5
        assert features.loc[features.index[0], "macd_macd_hist_phash_macd"] == 0.7

    def test_close_and_features_aligned_on_common_timestamps(
        self, tmp_path: pathlib.Path
    ) -> None:
        """Extra close rows without matching features are excluded."""
        db_path = tmp_path / "test_align.duckdb"
        conn = duckdb.connect(str(db_path))
        _seed_ohlcv_and_stage(conn)
        conn.execute(
            "INSERT INTO ohlcv_15s VALUES "
            "('2024-01-03 10:00:00', 'ES', 4505.0, 4506.0, 4504.0, 4505.5, 200)"
        )
        conn.close()

        close, features = load_features(
            database_path=db_path,
            symbol="ES",
            timeframe="15s",
            source_model="ohlcv_15s",
        )

        assert len(close) == 2  # only timestamps with features
        assert list(close.index) == list(features.index)

    def test_returns_empty_frame_when_stage_table_missing(self, tmp_path: pathlib.Path) -> None:
        """Missing indicator_feature_stage raises a useful error."""
        db_path = tmp_path / "test_missing.duckdb"
        conn = duckdb.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE ohlcv_15s (
                datetime TIMESTAMP NOT NULL,
                symbol VARCHAR NOT NULL,
                close DOUBLE
            )
            """
        )
        conn.execute(
            "INSERT INTO ohlcv_15s VALUES ('2024-01-03 09:30:00', 'ES', 4500.5)"
        )
        conn.close()

        with pytest.raises(RuntimeError, match="indicator_feature_stage"):
            load_features(
                database_path=db_path,
                symbol="ES",
                timeframe="15s",
                source_model="ohlcv_15s",
            )
