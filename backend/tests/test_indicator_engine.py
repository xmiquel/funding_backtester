"""Tests for indicator computation and metadata behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from funding_backtester.indicators.engine import (
    IndicatorComputationError,
    compute_indicator_batch,
    compute_indicator_series,
)
from funding_backtester.indicators.registry import describe_indicator


class FakeSeries(list):
    def __sub__(self, other: FakeSeries) -> FakeSeries:
        return FakeSeries([left - right for left, right in zip(self, other, strict=True)])

    def rolling(self, length: int) -> FakeSeries:
        values = [None] * (length - 1)
        for index in range(length - 1, len(self)):
            window = self[index - length + 1 : index + 1]
            values.append(float(sum(window)) / length)
        return FakeSeries(values)

    def mean(self) -> float:
        return float(sum(value for value in self if value is not None)) / len(self)

    def ewm(self, span: int, adjust: bool = False) -> SimpleNamespace:
        alpha = 2 / (span + 1)
        values = [self[0]]
        for value in self[1:]:
            values.append(values[-1] + alpha * (value - values[-1]))
        return SimpleNamespace(mean=lambda: FakeSeries(values))


class FakeFrame(dict):
    def assign(self, **kwargs: object) -> FakeFrame:
        updated = FakeFrame(self)
        updated.update(kwargs)
        return updated


def _sample_frame() -> FakeFrame:
    return FakeFrame(
        {"close": FakeSeries([100.0, 101.0, 102.0, 103.0, 104.0]), "volume": [10, 11, 12, 13, 14]}
    )


def test_compute_indicator_series_uses_cataloged_boundary() -> None:
    result = compute_indicator_series("ema", _sample_frame())

    assert result.name == "ema"
    assert result.columns == ("ema",)
    assert result.frame["ema"] == pytest.approx(
        [100.0, 100.090909, 100.264463, 100.513148, 100.830135], rel=1e-6
    )


def test_compute_indicator_series_produces_all_cataloged_protocol_macd_outputs() -> None:
    request = describe_indicator("macd")

    result = compute_indicator_series("macd", _sample_frame())

    assert result.columns == request.outputs
    assert tuple(output for output in request.outputs if output in result.frame) == request.outputs
    assert result.frame["macd"] == pytest.approx(
        [0.0, 0.079772, 0.221135, 0.409141, 0.631548], abs=1e-6
    )
    assert result.frame["macd_signal"] == pytest.approx(
        [0.0, 0.015954, 0.05699, 0.12742, 0.228246], abs=1e-6
    )
    assert result.frame["macd_hist"] == pytest.approx(
        [0.0, 0.063818, 0.164144, 0.28172, 0.403302], abs=1e-6
    )


def test_compute_indicator_series_rejects_non_cataloged_parameters() -> None:
    with pytest.raises(ValueError, match="Unsupported parameters for ema"):
        compute_indicator_series("ema", _sample_frame(), parameters={"length": 3})


def test_compute_indicator_series_rejects_unknown_indicator() -> None:
    with pytest.raises(ValueError, match="Unsupported indicator: unknown"):
        compute_indicator_series("unknown", _sample_frame())


def test_compute_indicator_batch_returns_deterministic_results() -> None:
    results = compute_indicator_batch(["rsi", "ema"], _sample_frame())

    assert [result.name for result in results] == ["rsi", "ema"]
    assert results[0].frame["rsi"] == 0.0
    assert results[1].frame["ema"][-1] == pytest.approx(100.83013455365071, rel=1e-4)


def _ohlcv_frame(rows: int = 40) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [100.0 + index for index in range(rows)],
            "high": [102.0 + index for index in range(rows)],
            "low": [99.0 + index for index in range(rows)],
            "close": [101.0 + index for index in range(rows)],
            "volume": [1000 + index for index in range(rows)],
        }
    )


def test_macd_catalog_min_lookback_covers_all_outputs() -> None:
    request = describe_indicator("macd")
    result = compute_indicator_series("macd", _ohlcv_frame())

    first_complete_index = result.frame[list(request.outputs)].dropna().index[0]

    assert request.min_lookback == 34
    assert first_complete_index == 33


def test_compute_indicator_series_produces_all_cataloged_pandas_outputs() -> None:
    frame = _ohlcv_frame()

    results = {
        name: compute_indicator_series(name, frame)
        for name in ("sma", "ema", "rsi", "macd", "atr", "bbands")
    }

    assert results["sma"].columns == ("sma",)
    assert results["sma"].frame["sma"].iloc[19] == pytest.approx(110.5)
    assert results["ema"].columns == ("ema",)
    assert results["ema"].frame["ema"].iloc[20] == pytest.approx(111.0)
    assert results["rsi"].columns == ("rsi",)
    assert results["rsi"].frame["rsi"].iloc[-1] == pytest.approx(100.0)
    assert results["macd"].columns == ("macd", "macd_signal", "macd_hist")
    assert results["macd"].frame["macd"].iloc[33] == pytest.approx(7.0)
    assert results["macd"].frame["macd_signal"].iloc[33] == pytest.approx(7.0)
    assert results["macd"].frame["macd_hist"].iloc[33] == pytest.approx(0.0)
    assert results["atr"].columns == ("atr",)
    assert results["atr"].frame["atr"].iloc[-1] == pytest.approx(3.0)
    assert results["bbands"].columns == ("bbands_lower", "bbands_middle", "bbands_upper")
    assert results["bbands"].frame["bbands_lower"].iloc[19] == pytest.approx(98.967437)
    assert results["bbands"].frame["bbands_middle"].iloc[19] == pytest.approx(110.5)
    assert results["bbands"].frame["bbands_upper"].iloc[19] == pytest.approx(122.032563)


def test_compute_indicator_series_records_backend_metadata() -> None:
    result = compute_indicator_series("sma", _ohlcv_frame())

    assert result.metadata["pandas_ta_classic_version"]
    assert isinstance(result.metadata["talib_available"], bool)
    assert "talib_version" in result.metadata
    assert result.metadata["talib_used"] is False


def test_compute_indicator_series_keeps_insufficient_lookback_rows_empty() -> None:
    bbands = compute_indicator_series("bbands", _ohlcv_frame(rows=19))
    macd = compute_indicator_series("macd", _ohlcv_frame(rows=33))

    assert bbands.frame[["bbands_lower", "bbands_middle", "bbands_upper"]].isna().all().all()
    assert macd.frame[["macd", "macd_signal", "macd_hist"]].isna().all().all()


def test_compute_indicator_series_rejects_invalid_ohlcv_frames_with_context() -> None:
    with pytest.raises(IndicatorComputationError, match="sma.*empty OHLCV frame"):
        compute_indicator_series("sma", _ohlcv_frame(rows=0))

    with pytest.raises(
        IndicatorComputationError,
        match="atr.*missing required OHLCV columns: high",
    ):
        compute_indicator_series("atr", _ohlcv_frame().drop(columns=["high"]))
