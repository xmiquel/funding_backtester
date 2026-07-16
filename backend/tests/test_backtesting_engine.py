from __future__ import annotations

from decimal import Decimal
from math import inf, nan
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
from funding_backtester.backtesting.engine import execute_next_bar_open
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
        "BacktestFill",
        "BacktestMetadata",
        "BacktestResult",
        "BacktestRunSummary",
        "BacktestTrade",
        "BacktestValidationError",
        "build_signal_frame",
        "execute_next_bar_open",
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


@pytest.mark.parametrize(
    "parameters",
    [
        {"payload": b"binary"},
        {"payload": nan},
        {"payload": inf},
        {1: "numeric key"},
        {1: "one", "1": "string one"},
        {"nested": {2: "numeric key"}},
    ],
)
def test_backtest_metadata_rejects_values_and_keys_that_cannot_be_canonicalized(
    parameters: dict[object, object],
) -> None:
    with pytest.raises(BacktestValidationError, match="parameters"):
        BacktestMetadata(
            input_snapshot_id="snapshot-123",
            code_revision="abc123",
            parameters=parameters,
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


def _execution_inputs() -> tuple[pd.Series, pd.Series, BacktestConfig, BacktestMetadata]:
    index = pd.date_range("2026-01-01", periods=8, freq="15s")
    close = pd.Series([1, 1, 1, 2, 3, 4, 1, 0], index=index)
    open_prices = pd.Series([100, 100, 100, 100, 110, 120, 90, 80], index=index)
    config = BacktestConfig(
        source_model="ohlcv_15s",
        symbol="ES",
        timeframe="15s",
        fast_window=2,
        slow_window=3,
        commission_bps=Decimal("10"),
        slippage_bps=Decimal("5"),
        initial_cash=Decimal("10000"),
    )
    metadata = BacktestMetadata(input_snapshot_id="snapshot-123", code_revision="abc123")
    return close, open_prices, config, metadata


def test_execute_next_bar_open_fills_crossover_on_following_open_with_costs() -> None:
    close, open_prices, config, metadata = _execution_inputs()

    result = execute_next_bar_open(close, open_prices, config=config, metadata=metadata)

    assert result.summary.run_id == "run-0858586d4df1770a"
    assert [(fill.side, fill.signal_timestamp, fill.fill_timestamp) for fill in result.fills] == [
        ("buy", close.index[3], close.index[4]),
        ("sell", close.index[6], close.index[7]),
    ]
    assert result.fills[0].fill_price == Decimal("110.055")
    assert result.fills[0].commission == Decimal("0.110055")
    assert result.trades[0].net_pnl == Decimal("-30.285015")


def test_execute_next_bar_open_reports_signal_without_next_bar() -> None:
    index = pd.date_range("2026-01-01", periods=6, freq="15s")
    close = pd.Series([3, 2, 1, 1, 1, 2], index=index)
    open_prices = pd.Series([10, 10, 10, 10, 10, 20], index=index)
    config = BacktestConfig(
        source_model="ohlcv_15s",
        symbol="ES",
        timeframe="15s",
        fast_window=2,
        slow_window=3,
        commission_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        initial_cash=Decimal("10000"),
    )
    metadata = BacktestMetadata(input_snapshot_id="snapshot-123", code_revision="abc123")

    result = execute_next_bar_open(close, open_prices, config=config, metadata=metadata)

    assert result.fills == ()
    assert result.unfilled_signals == (("buy", index[-1]),)


def test_execute_next_bar_open_leaves_final_position_open_without_synthetic_exit() -> None:
    index = pd.date_range("2026-01-01", periods=6, freq="15s")
    close = pd.Series([1, 1, 1, 2, 3, 4], index=index)
    open_prices = pd.Series([100, 100, 100, 100, 110, 120], index=index)
    config = BacktestConfig(
        source_model="ohlcv_15s",
        symbol="ES",
        timeframe="15s",
        fast_window=2,
        slow_window=3,
        commission_bps=Decimal("0"),
        slippage_bps=Decimal("0"),
        initial_cash=Decimal("10000"),
    )
    metadata = BacktestMetadata(input_snapshot_id="snapshot-123", code_revision="abc123")

    result = execute_next_bar_open(close, open_prices, config=config, metadata=metadata)

    assert [(fill.side, fill.fill_timestamp) for fill in result.fills] == [("buy", index[4])]
    assert result.trades == ()
    assert result.unfilled_signals == ()


@pytest.mark.parametrize(
    "open_prices",
    [
        pd.Series(dtype="float64"),
        pd.Series([100, 101], index=pd.date_range("2026-01-01", periods=2, freq="15s")),
        pd.Series([100, "invalid"], index=pd.date_range("2026-01-01", periods=2, freq="15s")),
        pd.Series([100, nan], index=pd.date_range("2026-01-01", periods=2, freq="15s")),
        pd.Series([100, -1], index=pd.date_range("2026-01-01", periods=2, freq="15s")),
    ],
)
def test_execute_next_bar_open_rejects_invalid_open_prices(open_prices: pd.Series) -> None:
    close, _, config, metadata = _execution_inputs()

    with pytest.raises(BacktestValidationError, match="open_prices"):
        execute_next_bar_open(close, open_prices, config=config, metadata=metadata)


def test_execute_next_bar_open_rejects_non_series_close_before_index_access() -> None:
    _, open_prices, config, metadata = _execution_inputs()

    with pytest.raises(BacktestValidationError, match="close"):
        execute_next_bar_open(
            cast(pd.Series, [1, 2]), open_prices, config=config, metadata=metadata
        )


def test_execute_next_bar_open_rejects_incompatible_open_price_index() -> None:
    close, open_prices, config, metadata = _execution_inputs()
    incompatible = open_prices.rename(
        index={open_prices.index[0]: open_prices.index[0] + pd.Timedelta(seconds=1)}
    )

    with pytest.raises(BacktestValidationError, match="same index"):
        execute_next_bar_open(close, incompatible, config=config, metadata=metadata)


def test_execute_next_bar_open_is_deterministic_for_same_inputs() -> None:
    close, open_prices, config, metadata = _execution_inputs()

    first = execute_next_bar_open(close, open_prices, config=config, metadata=metadata)
    second = execute_next_bar_open(close, open_prices, config=config, metadata=metadata)

    assert first == second


def test_execute_next_bar_open_canonicalizes_frozenset_metadata_deterministically() -> None:
    close, open_prices, config, metadata = _execution_inputs()
    metadata_with_frozenset = BacktestMetadata(
        input_snapshot_id=metadata.input_snapshot_id,
        code_revision=metadata.code_revision,
        parameters={"symbols": frozenset({"ES", "NQ"})},
    )
    metadata_with_reordered_frozenset = BacktestMetadata(
        input_snapshot_id=metadata.input_snapshot_id,
        code_revision=metadata.code_revision,
        parameters={"symbols": frozenset({"NQ", "ES"})},
    )

    first = execute_next_bar_open(
        close,
        open_prices,
        config=config,
        metadata=metadata_with_frozenset,
    )
    second = execute_next_bar_open(
        close,
        open_prices,
        config=config,
        metadata=metadata_with_reordered_frozenset,
    )

    assert first.summary.run_id == second.summary.run_id
