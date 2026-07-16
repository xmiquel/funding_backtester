from __future__ import annotations

from decimal import Decimal
from typing import cast

import pandas as pd
import pytest

import funding_backtester.backtesting as backtesting
from funding_backtester.backtesting.contracts import (
    BacktestConfig,
    BacktestMetadata,
    BacktestValidationError,
    validate_window_pair,
)
from funding_backtester.backtesting.strategy import build_signal_frame


class MutableParameter:
    def __init__(self, value: int) -> None:
        self.value = value


def test_backtesting_public_api_exports() -> None:
    assert backtesting.BacktestConfig is BacktestConfig
    assert backtesting.BacktestMetadata is BacktestMetadata
    assert backtesting.BacktestValidationError is BacktestValidationError
    assert backtesting.build_signal_frame is build_signal_frame
    assert backtesting.__all__ == [
        "BacktestConfig",
        "BacktestMetadata",
        "BacktestValidationError",
        "build_signal_frame",
    ]


def test_backtest_config_constructs_valid_contract() -> None:
    config = BacktestConfig(
        source_model="ohlcv_15s",
        symbol="ES",
        timeframe="15s",
        fast_window=2,
        slow_window=3,
        commission_bps=Decimal("1.5"),
        slippage_bps=Decimal("0.25"),
        initial_cash=Decimal("10000"),
    )

    assert config.source_model == "ohlcv_15s"
    assert config.symbol == "ES"
    assert config.fast_window == 2
    assert config.slow_window == 3
    assert config.strategy_version == "ma-crossover-v1"
    assert config.schema_version == "v1"


def test_backtest_metadata_constructs_valid_contract() -> None:
    metadata = BacktestMetadata(input_snapshot_id="snapshot-123", code_revision="abc123")

    assert metadata.input_snapshot_id == "snapshot-123"
    assert metadata.code_revision == "abc123"
    assert metadata.parameters == {}
    assert metadata.schema_version == "v1"


def test_backtest_metadata_parameters_are_copied_on_construction() -> None:
    parameters = {"threshold": 2}

    metadata = BacktestMetadata(
        input_snapshot_id="snapshot-123",
        code_revision="abc123",
        parameters=parameters,
    )

    parameters["threshold"] = 99

    assert metadata.parameters["threshold"] == 2


def test_backtest_metadata_parameters_are_immutable_after_construction() -> None:
    metadata = BacktestMetadata(input_snapshot_id="snapshot-123", code_revision="abc123")

    with pytest.raises(TypeError):
        metadata.parameters["threshold"] = 2


def test_backtest_metadata_parameters_are_deeply_immutable_after_construction() -> None:
    parameters = {
        "risk": {
            "thresholds": {"entry": 2, "exit": 1},
            "weights": [1, 2],
        }
    }

    metadata = BacktestMetadata(
        input_snapshot_id="snapshot-123",
        code_revision="abc123",
        parameters=parameters,
    )

    parameters["risk"]["thresholds"]["entry"] = 99
    parameters["risk"]["weights"].append(3)

    assert metadata.parameters["risk"]["thresholds"]["entry"] == 2
    assert metadata.parameters["risk"]["weights"] == (1, 2)

    with pytest.raises(TypeError):
        metadata.parameters["risk"]["thresholds"]["entry"] = 99

    with pytest.raises(AttributeError):
        metadata.parameters["risk"]["weights"].append(3)


def test_backtest_metadata_rejects_unsupported_mutable_parameter_values() -> None:
    with pytest.raises(BacktestValidationError, match="unsupported mutable value"):
        BacktestMetadata(
            input_snapshot_id="snapshot-123",
            code_revision="abc123",
            parameters={"custom": MutableParameter(2)},
        )


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_backtest_config_rejects_non_finite_decimal_values(value: Decimal) -> None:
    with pytest.raises(BacktestValidationError, match="must be finite"):
        BacktestConfig(
            source_model="ohlcv_15s",
            symbol="ES",
            timeframe="15s",
            fast_window=2,
            slow_window=3,
            commission_bps=value,
            slippage_bps=Decimal("0"),
            initial_cash=Decimal("10000"),
        )


def test_contracts_normalize_type_errors_to_backtest_validation_error() -> None:
    with pytest.raises(BacktestValidationError, match="commission_bps must be a Decimal"):
        BacktestConfig(
            source_model="ohlcv_15s",
            symbol="ES",
            timeframe="15s",
            fast_window=2,
            slow_window=3,
            commission_bps=cast(Decimal, "invalid"),
            slippage_bps=Decimal("0"),
            initial_cash=Decimal("10000"),
        )


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("strategy_version", {"strategy_version": ""}),
        ("strategy_version", {"strategy_version": "   "}),
        ("strategy_version", {"strategy_version": "\t"}),
        ("schema_version", {"schema_version": ""}),
        ("schema_version", {"schema_version": "   "}),
        ("schema_version", {"schema_version": "\t"}),
    ],
)
def test_backtest_config_rejects_blank_version_fields(
    field_name: str,
    field_value: dict[str, str],
) -> None:
    overrides = field_value

    with pytest.raises(BacktestValidationError, match=f"{field_name} must be non-empty"):
        BacktestConfig(
            source_model="ohlcv_15s",
            symbol="ES",
            timeframe="15s",
            fast_window=2,
            slow_window=3,
            commission_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            initial_cash=Decimal("10000"),
            **overrides,
        )


@pytest.mark.parametrize("schema_version", ["", "   ", "\t"])
def test_backtest_metadata_rejects_blank_schema_version(schema_version: str) -> None:
    with pytest.raises(BacktestValidationError, match="schema_version must be non-empty"):
        BacktestMetadata(
            input_snapshot_id="snapshot-123",
            code_revision="abc123",
            schema_version=schema_version,
        )


@pytest.mark.parametrize(
    ("factory", "field_name", "field_value"),
    [
        (BacktestConfig, "source_model", ""),
        (BacktestConfig, "symbol", "   "),
        (BacktestConfig, "timeframe", "\t"),
        (BacktestMetadata, "input_snapshot_id", ""),
        (BacktestMetadata, "code_revision", "   "),
    ],
)
def test_contracts_reject_blank_identity_fields(
    factory: type[BacktestConfig] | type[BacktestMetadata],
    field_name: str,
    field_value: str,
) -> None:
    kwargs = (
        dict(
            source_model="ohlcv_15s",
            symbol="ES",
            timeframe="15s",
            fast_window=2,
            slow_window=3,
            commission_bps=Decimal("1.5"),
            slippage_bps=Decimal("0.25"),
            initial_cash=Decimal("10000"),
        )
        if factory is BacktestConfig
        else dict(input_snapshot_id="snapshot-123", code_revision="abc123")
    )
    kwargs[field_name] = field_value

    with pytest.raises(BacktestValidationError, match="non-empty"):
        factory(**kwargs)


@pytest.mark.parametrize(
    ("fast_window", "slow_window", "expected_message"),
    [
        (0, 3, "fast_window and slow_window must be positive"),
        (2, 0, "fast_window and slow_window must be positive"),
        (3, 3, "fast_window must be smaller than slow_window"),
    ],
)
def test_validate_window_pair_rejects_invalid_windows(
    fast_window: int,
    slow_window: int,
    expected_message: str,
) -> None:
    with pytest.raises(BacktestValidationError, match=expected_message):
        validate_window_pair(fast_window, slow_window)


def test_backtest_config_rejects_fast_window_that_is_not_smaller_than_slow_window() -> None:
    with pytest.raises(BacktestValidationError, match="smaller than slow_window"):
        BacktestConfig(
            source_model="ohlcv_15s",
            symbol="ES",
            timeframe="15s",
            fast_window=3,
            slow_window=3,
            commission_bps=Decimal("0"),
            slippage_bps=Decimal("0"),
            initial_cash=Decimal("10000"),
        )


@pytest.mark.parametrize(
    ("commission_bps", "slippage_bps", "initial_cash", "expected_message"),
    [
        (Decimal("-1"), Decimal("0"), Decimal("10000"), "non-negative"),
        (Decimal("0"), Decimal("-0.5"), Decimal("10000"), "non-negative"),
        (Decimal("0"), Decimal("0"), Decimal("0"), "must be positive"),
    ],
)
def test_backtest_config_rejects_invalid_costs_or_cash(
    commission_bps: Decimal,
    slippage_bps: Decimal,
    initial_cash: Decimal,
    expected_message: str,
) -> None:
    with pytest.raises(BacktestValidationError, match=expected_message):
        BacktestConfig(
            source_model="ohlcv_15s",
            symbol="ES",
            timeframe="15s",
            fast_window=2,
            slow_window=3,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            initial_cash=initial_cash,
        )


@pytest.mark.parametrize(
    ("signal_index", "expected_fast_ma", "expected_slow_ma", "bullish", "bearish"),
    [
        (3, 1.5, 1.3333333333, True, False),
        (6, 2.5, 2.6666666667, False, True),
    ],
)
def test_build_signal_frame_marks_crosses(
    signal_index: int,
    expected_fast_ma: float,
    expected_slow_ma: float,
    bullish: bool,
    bearish: bool,
) -> None:
    close = pd.Series(
        [1, 1, 1, 2, 3, 4, 1, 0], index=pd.date_range("2026-01-01", periods=8, freq="15s")
    )

    frame = build_signal_frame(close, fast_window=2, slow_window=3)

    assert list(frame.columns) == ["close", "fast_ma", "slow_ma", "bullish_cross", "bearish_cross"]
    assert frame.loc[close.index[signal_index], "fast_ma"] == pytest.approx(expected_fast_ma)
    assert frame.loc[close.index[signal_index], "slow_ma"] == pytest.approx(expected_slow_ma)
    assert bool(frame.loc[close.index[signal_index], "bullish_cross"]) is bullish
    assert bool(frame.loc[close.index[signal_index], "bearish_cross"]) is bearish


@pytest.mark.parametrize(
    ("close", "expected_fast_ma", "expected_slow_ma", "is_empty"),
    [
        (pd.Series(dtype="float64"), [], [], True),
        (
            pd.Series([1, 2], index=pd.date_range("2026-01-01", periods=2, freq="15s")),
            [True, False],
            [True, True],
            False,
        ),
    ],
)
def test_build_signal_frame_handles_incomplete_input(
    close: pd.Series,
    expected_fast_ma: list[bool],
    expected_slow_ma: list[bool],
    is_empty: bool,
) -> None:
    frame = build_signal_frame(close, fast_window=2, slow_window=3)

    assert list(frame.columns) == ["close", "fast_ma", "slow_ma", "bullish_cross", "bearish_cross"]
    assert frame.empty is is_empty
    if not is_empty:
        assert frame["fast_ma"].isna().tolist() == expected_fast_ma
        assert frame["slow_ma"].isna().tolist() == expected_slow_ma
        assert not frame["bullish_cross"].any()
        assert not frame["bearish_cross"].any()


def test_build_signal_frame_returns_no_crosses_when_input_never_crosses() -> None:
    close = pd.Series([4, 3, 2, 1], index=pd.date_range("2026-01-01", periods=4, freq="15s"))

    frame = build_signal_frame(close, fast_window=2, slow_window=3)

    assert not frame["bullish_cross"].any()
    assert not frame["bearish_cross"].any()


def test_build_signal_frame_is_deterministic_for_same_input() -> None:
    close = pd.Series(
        [1, 1, 1, 2, 3, 4, 1, 0], index=pd.date_range("2026-01-01", periods=8, freq="15s")
    )

    first = build_signal_frame(close, fast_window=2, slow_window=3)
    second = build_signal_frame(close, fast_window=2, slow_window=3)

    pd.testing.assert_frame_equal(first, second)


@pytest.mark.parametrize(
    "index",
    [
        pd.to_datetime(["2026-01-01 00:00:15", "2026-01-01 00:00:00"]),
        pd.to_datetime(["2026-01-01", "2026-01-01"]),
    ],
)
def test_build_signal_frame_rejects_non_strict_temporal_index(index: pd.DatetimeIndex) -> None:
    close = pd.Series([1, 2], index=index)

    with pytest.raises(BacktestValidationError, match="strictly increasing and unique"):
        build_signal_frame(close, fast_window=2, slow_window=3)


def test_build_signal_frame_rejects_non_temporal_index() -> None:
    close = pd.Series([1, 2], index=[0, 1])

    with pytest.raises(BacktestValidationError, match="DatetimeIndex"):
        build_signal_frame(close, fast_window=2, slow_window=3)
