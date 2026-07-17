from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from math import isfinite
from types import MappingProxyType
from typing import Literal


class BacktestValidationError(ValueError):
    """Raised when backtesting inputs violate the public contract."""

    pass


class BacktestResultValidationError(BacktestValidationError):
    """Raised when an execution result violates its public contract."""

    pass


def validate_window_pair(fast_window: int, slow_window: int) -> None:
    if (
        isinstance(fast_window, bool)
        or isinstance(slow_window, bool)
        or not isinstance(fast_window, int)
        or not isinstance(slow_window, int)
    ):
        raise BacktestValidationError("fast_window and slow_window must be integers")
    if fast_window <= 0 or slow_window <= 0:
        raise BacktestValidationError("fast_window and slow_window must be positive")
    if fast_window >= slow_window:
        raise BacktestValidationError("fast_window must be smaller than slow_window")


def _validate_non_empty_text(field_name: str, value: str) -> None:
    if not isinstance(value, str):
        raise BacktestValidationError(f"{field_name} must be a string")
    if not value.strip():
        raise BacktestValidationError(f"{field_name} must be non-empty")


def _validate_decimal(field_name: str, value: Decimal) -> None:
    if not isinstance(value, Decimal):
        raise BacktestValidationError(f"{field_name} must be a Decimal")
    if not value.is_finite():
        raise BacktestValidationError(f"{field_name} must be finite")


def _freeze_parameter_value(value: object) -> object:
    if isinstance(value, Mapping):
        frozen: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise BacktestValidationError("parameters keys must be strings")
            frozen[key] = _freeze_parameter_value(item)
        return MappingProxyType(frozen)
    if isinstance(value, list):
        return tuple(_freeze_parameter_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_parameter_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_parameter_value(item) for item in value)
    if isinstance(value, float) and not isfinite(value):
        raise BacktestValidationError("parameters contains non-finite float value")
    if value is None or isinstance(value, (bool, int, float, str, Decimal)):
        return value
    if isinstance(value, bytes):
        raise BacktestValidationError("parameters contains unsupported bytes value")
    raise BacktestValidationError(
        f"parameters contains unsupported mutable value of type {type(value).__name__}"
    )


def _freeze_parameters(parameters: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(parameters, Mapping):
        raise BacktestValidationError("parameters must be a mapping")
    frozen = _freeze_parameter_value(parameters)
    if not isinstance(frozen, Mapping):
        raise BacktestValidationError("parameters must be a mapping")
    return frozen


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Validated strategy, cost, and capital settings for one backtest run."""

    source_model: str
    symbol: str
    timeframe: str
    fast_window: int
    slow_window: int
    commission_bps: Decimal
    slippage_bps: Decimal
    initial_cash: Decimal
    strategy_version: str = "ma-crossover-v1"
    schema_version: str = "v1"

    def __post_init__(self) -> None:
        _validate_non_empty_text("source_model", self.source_model)
        _validate_non_empty_text("symbol", self.symbol)
        _validate_non_empty_text("timeframe", self.timeframe)
        _validate_non_empty_text("strategy_version", self.strategy_version)
        _validate_non_empty_text("schema_version", self.schema_version)
        validate_window_pair(self.fast_window, self.slow_window)
        _validate_decimal("commission_bps", self.commission_bps)
        _validate_decimal("slippage_bps", self.slippage_bps)
        _validate_decimal("initial_cash", self.initial_cash)
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise BacktestValidationError("commission_bps and slippage_bps must be non-negative")
        if self.initial_cash <= 0:
            raise BacktestValidationError("initial_cash must be positive")


@dataclass(frozen=True, slots=True)
class BacktestMetadata:
    """Immutable reproducibility identity and JSON-canonicalizable parameters."""

    input_snapshot_id: str
    code_revision: str
    parameters: Mapping[str, object] = field(default_factory=dict)
    schema_version: str = "v1"

    def __post_init__(self) -> None:
        _validate_non_empty_text("input_snapshot_id", self.input_snapshot_id)
        _validate_non_empty_text("code_revision", self.code_revision)
        _validate_non_empty_text("schema_version", self.schema_version)
        object.__setattr__(self, "parameters", _freeze_parameters(self.parameters))


@dataclass(frozen=True, slots=True)
class BacktestRunSummary:
    """Run-level outcome and reproducibility fields."""

    run_id: str
    schema_version: str
    strategy_version: str
    input_snapshot_id: str
    code_revision: str
    commission_bps: Decimal
    slippage_bps: Decimal
    unfilled_signal_count: int


@dataclass(frozen=True, slots=True)
class BacktestFill:
    """One-unit entry or exit fill, including price-impact and commission costs."""

    run_id: str
    side: Literal["buy", "sell"]
    signal_timestamp: datetime
    fill_timestamp: datetime
    fill_price: Decimal
    commission: Decimal
    slippage: Decimal


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    """Completed one-unit long trade assembled from an entry and an exit fill."""

    run_id: str
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_price: Decimal
    exit_price: Decimal
    commission: Decimal
    slippage: Decimal
    net_pnl: Decimal
    quantity: Decimal = Decimal("1")


@dataclass(frozen=True, slots=True)
class BacktestResult:
    """Immutable execution output containing the summary, fills, trades, and signals."""

    summary: BacktestRunSummary
    fills: tuple[BacktestFill, ...]
    trades: tuple[BacktestTrade, ...]
    unfilled_signals: tuple[tuple[Literal["buy", "sell"], datetime], ...]


def _validate_result_timestamp(field_name: str, value: object) -> datetime:
    if not isinstance(value, datetime):
        raise BacktestResultValidationError(f"{field_name} must be a datetime")
    return value


def _validate_result_decimal(field_name: str, value: object) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise BacktestResultValidationError(f"{field_name} must be a finite Decimal")
    return value


def _validate_result_text(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise BacktestResultValidationError(f"{field_name} must be non-empty")


def _validate_trade(trade: BacktestTrade, run_id: str) -> None:
    if not isinstance(trade.run_id, str) or not trade.run_id.strip() or trade.run_id != run_id:
        raise BacktestResultValidationError("trade.run_id must match summary.run_id")
    entry_timestamp = _validate_result_timestamp("trade.entry_timestamp", trade.entry_timestamp)
    exit_timestamp = _validate_result_timestamp("trade.exit_timestamp", trade.exit_timestamp)
    if entry_timestamp >= exit_timestamp:
        raise BacktestResultValidationError("trade timestamps must be ordered")
    entry_price = _validate_result_decimal("trade.entry_price", trade.entry_price)
    exit_price = _validate_result_decimal("trade.exit_price", trade.exit_price)
    commission = _validate_result_decimal("trade.commission", trade.commission)
    slippage = _validate_result_decimal("trade.slippage", trade.slippage)
    net_pnl = _validate_result_decimal("trade.net_pnl", trade.net_pnl)
    quantity = _validate_result_decimal("trade.quantity", trade.quantity)
    if min(entry_price, exit_price, commission, slippage, quantity) < 0:
        raise BacktestResultValidationError(
            "trade prices, costs, and quantity must be non-negative"
        )
    if quantity != Decimal("1"):
        raise BacktestResultValidationError("trade quantity must be exactly one unit")
    expected_pnl = (exit_price - entry_price) * quantity - commission - slippage
    if net_pnl != expected_pnl:
        raise BacktestResultValidationError("trade net_pnl does not match prices and costs")


def validate_backtest_result(result: BacktestResult) -> None:
    """Validate result-level invariants before downstream persistence."""
    if not isinstance(result, BacktestResult):
        raise BacktestResultValidationError("result must be a BacktestResult")
    summary = result.summary
    if not isinstance(summary, BacktestRunSummary):
        raise BacktestResultValidationError("result.summary must be a BacktestRunSummary")
    _validate_result_text("summary.run_id", summary.run_id)
    _validate_result_text("summary.schema_version", summary.schema_version)
    _validate_result_text("summary.strategy_version", summary.strategy_version)
    _validate_result_text("summary.input_snapshot_id", summary.input_snapshot_id)
    _validate_result_text("summary.code_revision", summary.code_revision)
    for field_name in ("commission_bps", "slippage_bps"):
        value = _validate_result_decimal(f"summary.{field_name}", getattr(summary, field_name))
        if value < 0:
            raise BacktestResultValidationError("summary costs must be non-negative")
    if not isinstance(summary.unfilled_signal_count, int) or summary.unfilled_signal_count < 0:
        raise BacktestResultValidationError("summary.unfilled_signal_count must be non-negative")
    if not isinstance(result.fills, tuple) or not all(
        isinstance(fill, BacktestFill) for fill in result.fills
    ):
        raise BacktestResultValidationError("result fills must be BacktestFill values")
    if not isinstance(result.trades, tuple):
        raise BacktestResultValidationError("result trades must be a tuple")
    for trade in result.trades:
        if not isinstance(trade, BacktestTrade):
            raise BacktestResultValidationError("result trades must be BacktestTrade values")
        _validate_trade(trade, summary.run_id)
    if not isinstance(result.unfilled_signals, tuple):
        raise BacktestResultValidationError("result.unfilled_signals must be a tuple")
    if summary.unfilled_signal_count != len(result.unfilled_signals):
        raise BacktestResultValidationError("unfilled signal count does not match results")
    for signal in result.unfilled_signals:
        if not isinstance(signal, tuple) or len(signal) != 2:
            raise BacktestResultValidationError("unfilled signals must contain side and timestamp")
        side, timestamp = signal
        if side not in ("buy", "sell"):
            raise BacktestResultValidationError("unfilled signal side must be buy or sell")
        _validate_result_timestamp("unfilled signal timestamp", timestamp)
