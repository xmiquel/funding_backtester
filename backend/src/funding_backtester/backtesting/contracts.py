from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType


class BacktestValidationError(ValueError):
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
        return MappingProxyType({key: _freeze_parameter_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_parameter_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_parameter_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_parameter_value(item) for item in value)
    if value is None or isinstance(value, (bool, int, float, str, bytes, Decimal)):
        return value
    raise BacktestValidationError(
        f"parameters contains unsupported mutable value of type {type(value).__name__}"
    )


def _freeze_parameters(parameters: Mapping[str, object]) -> Mapping[str, object]:
    if not isinstance(parameters, Mapping):
        raise BacktestValidationError("parameters must be a mapping")
    return MappingProxyType(
        {key: _freeze_parameter_value(value) for key, value in parameters.items()}
    )


@dataclass(frozen=True, slots=True)
class BacktestConfig:
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
    input_snapshot_id: str
    code_revision: str
    parameters: Mapping[str, object] = field(default_factory=dict)
    schema_version: str = "v1"

    def __post_init__(self) -> None:
        _validate_non_empty_text("input_snapshot_id", self.input_snapshot_id)
        _validate_non_empty_text("code_revision", self.code_revision)
        _validate_non_empty_text("schema_version", self.schema_version)
        object.__setattr__(self, "parameters", _freeze_parameters(self.parameters))
