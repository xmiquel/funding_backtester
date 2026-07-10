"""Tests for catalog-only indicator registry metadata."""

from __future__ import annotations

import pytest

from funding_backtester import indicators
from funding_backtester.indicators.registry import (
    IndicatorRequest,
    describe_indicator,
    list_indicator_metadata,
    validate_indicator_request,
)


def test_validate_indicator_request_returns_catalog_metadata() -> None:
    request = validate_indicator_request("macd")

    assert request == IndicatorRequest(
        name="macd",
        parameters={"fastperiod": 12, "slowperiod": 26, "signalperiod": 9},
        outputs=("macd", "macd_signal", "macd_hist"),
        min_lookback=34,
    )


def test_validate_indicator_request_rejects_free_form_parameters() -> None:
    with pytest.raises(ValueError, match="Unsupported parameters for rsi"):
        validate_indicator_request("rsi", {"length": 7})


def test_list_indicator_metadata_is_stable_and_bounded() -> None:
    metadata = list_indicator_metadata()

    assert [item.name for item in metadata] == ["atr", "bbands", "ema", "macd", "rsi", "sma"]
    assert describe_indicator("bbands").outputs == (
        "bbands_lower",
        "bbands_middle",
        "bbands_upper",
    )


def test_package_root_exports_public_registry_contract() -> None:
    request = indicators.validate_indicator_request("macd")

    assert request == indicators.IndicatorRequest(
        name="macd",
        parameters={"fastperiod": 12, "slowperiod": 26, "signalperiod": 9},
        outputs=("macd", "macd_signal", "macd_hist"),
        min_lookback=34,
    )
    assert indicators.describe_indicator("bbands").outputs == (
        "bbands_lower",
        "bbands_middle",
        "bbands_upper",
    )
    assert [item.name for item in indicators.list_indicator_metadata()] == [
        "atr",
        "bbands",
        "ema",
        "macd",
        "rsi",
        "sma",
    ]
    with pytest.raises(ValueError, match="Unsupported parameters for rsi"):
        indicators.validate_indicator_request("rsi", {"length": 7})
