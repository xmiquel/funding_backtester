"""Tests for bounded indicator catalog and canonical parameter identity."""

from __future__ import annotations

import pytest

from funding_backtester.indicators.parameters import (
    INDICATOR_CATALOG,
    canonical_parameter_json,
    feature_id,
    get_indicator_definition,
    normalize_indicator_parameters,
    parameter_hash,
)


def test_indicator_catalog_is_bounded() -> None:
    assert set(INDICATOR_CATALOG) == {"sma", "ema", "rsi", "macd", "atr", "bbands"}


def test_known_indicator_parameters_are_normalized() -> None:
    definition = get_indicator_definition("macd")
    assert definition.library == "talib"
    assert definition.outputs == ("macd", "macd_signal", "macd_hist")
    assert definition.min_lookback == 34
    assert normalize_indicator_parameters("macd") == {
        "fastperiod": 12,
        "slowperiod": 26,
        "signalperiod": 9,
    }


def test_all_catalog_entries_define_outputs_and_lookback() -> None:
    assert get_indicator_definition("sma").outputs == ("sma",)
    assert get_indicator_definition("ema").outputs == ("ema",)
    assert get_indicator_definition("rsi").outputs == ("rsi",)
    assert get_indicator_definition("atr").outputs == ("atr",)
    assert get_indicator_definition("bbands").outputs == (
        "bbands_lower",
        "bbands_middle",
        "bbands_upper",
    )

    assert get_indicator_definition("bbands").min_lookback == 20


def test_unknown_indicator_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported indicator: unknown"):
        get_indicator_definition("unknown")


def test_free_form_parameter_override_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported parameters for ema: expected .* got .*",
    ):
        normalize_indicator_parameters("ema", {"length": 99})


def test_canonical_parameter_identity_is_stable() -> None:
    parameters = {"slowperiod": 26, "signalperiod": 9, "fastperiod": 12}

    canonical = canonical_parameter_json(parameters)

    assert canonical == '{"fastperiod":12,"signalperiod":9,"slowperiod":26}'
    assert parameter_hash(parameters) == parameter_hash(normalize_indicator_parameters("macd"))
    assert feature_id(
        source_model="ohlcv_1m",
        symbol="BTCUSDT",
        timeframe="1m",
        feature_name="macd",
        parameters=parameters,
        computation_version="indicator-v1",
    ) == feature_id(
        source_model="ohlcv_1m",
        symbol="BTCUSDT",
        timeframe="1m",
        feature_name="macd",
        parameters=normalize_indicator_parameters("macd"),
        computation_version="indicator-v1",
    )
