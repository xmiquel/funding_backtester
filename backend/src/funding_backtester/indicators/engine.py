"""Indicator computation boundary for feature generation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol

from funding_backtester.indicators.parameters import (
    get_indicator_definition,
    normalize_indicator_parameters,
)

PANDAS_MODULE = "pandas"


@dataclass(frozen=True, slots=True)
class IndicatorResult:
    name: str
    columns: tuple[str, ...]
    frame: object
    metadata: dict[str, object]


class IndicatorComputationError(ValueError):
    """Domain error raised when indicator computation cannot safely run."""


class IndicatorFrame(Protocol):
    def __getitem__(self, key: str) -> IndicatorSeries: ...

    def assign(self, **kwargs: object) -> IndicatorFrame: ...


class IndicatorSeries(Protocol):
    def __getitem__(self, key: int) -> float: ...

    def rolling(self, length: int) -> IndicatorSeries: ...

    def ewm(self, span: int, adjust: bool = False) -> IndicatorSeries: ...

    def mean(self) -> IndicatorSeries: ...

    def __sub__(self, other: IndicatorSeries) -> IndicatorSeries: ...


def _parameter_value(parameters: dict[str, object], key: str) -> int:
    value = parameters[key]
    if not isinstance(value, int):
        msg = f"Indicator parameter {key!r} must be an integer, got {type(value).__name__}"
        raise TypeError(msg)
    return value


def _backend_metadata(*, talib_used: bool) -> dict[str, object]:
    pandas_ta = import_module("pandas_ta_classic")
    try:
        import talib
    except ImportError:
        talib_available = False
        talib_version = None
    else:
        talib_available = True
        talib_version = talib.__version__
    return {
        "pandas_ta_classic_version": getattr(pandas_ta, "__version__", "unknown"),
        "talib_available": talib_available,
        "talib_version": talib_version,
        "talib_used": talib_used and talib_available,
    }


def _result(
    name: str,
    columns: tuple[str, ...],
    frame: object,
    *,
    talib_used: bool = False,
) -> IndicatorResult:
    return IndicatorResult(name, columns, frame, _backend_metadata(talib_used=talib_used))


def _is_pandas_frame(frame: object) -> bool:
    frame_type = type(frame)
    return frame_type.__name__ == "DataFrame" and frame_type.__module__ == PANDAS_MODULE


def _compute_pandas_indicator(
    name: str, frame: Any, parameters: dict[str, object]
) -> IndicatorResult:
    pd = import_module("pandas")
    import_module("pandas_ta_classic")
    output_frame = frame.copy()
    _validate_ohlcv_frame(name, output_frame)
    definition = get_indicator_definition(name)
    if len(output_frame) < definition.min_lookback:
        empty_frame = _empty_output_frame(output_frame, definition.outputs)
        return _result(name, definition.outputs, empty_frame)
    if name == "sma":
        series = output_frame.ta.sma(length=_parameter_value(parameters, "length"))
        return _result(name, ("sma",), output_frame.assign(sma=series))
    if name == "ema":
        series = output_frame.ta.ema(length=_parameter_value(parameters, "length"))
        return _result(name, ("ema",), output_frame.assign(ema=series))
    if name == "rsi":
        series = output_frame.ta.rsi(length=_parameter_value(parameters, "length"))
        return _result(name, ("rsi",), output_frame.assign(rsi=series))
    if name == "macd":
        macd = output_frame.ta.macd(
            fast=_parameter_value(parameters, "fastperiod"),
            slow=_parameter_value(parameters, "slowperiod"),
            signal=_parameter_value(parameters, "signalperiod"),
        )
        if macd is None:
            return _result(
                name,
                ("macd", "macd_signal", "macd_hist"),
                output_frame.assign(macd=pd.NA, macd_signal=pd.NA, macd_hist=pd.NA),
                talib_used=True,
            )
        return _result(
            name,
            ("macd", "macd_signal", "macd_hist"),
            output_frame.assign(
                macd=macd.iloc[:, 0],
                macd_hist=macd.iloc[:, 1],
                macd_signal=macd.iloc[:, 2],
            ),
            talib_used=True,
        )
    if name == "atr":
        series = output_frame.ta.atr(length=_parameter_value(parameters, "length"))
        return _result(name, ("atr",), output_frame.assign(atr=series))
    if name == "bbands":
        bands = output_frame.ta.bbands(
            length=_parameter_value(parameters, "length"),
            std=_parameter_value(parameters, "std"),
        )
        if bands is None:
            empty_frame = _empty_output_frame(output_frame, definition.outputs)
            return _result(name, definition.outputs, empty_frame)
        return _result(
            name,
            ("bbands_lower", "bbands_middle", "bbands_upper"),
            output_frame.assign(
                bbands_lower=bands.iloc[:, 0],
                bbands_middle=bands.iloc[:, 1],
                bbands_upper=bands.iloc[:, 2],
            ),
        )
    msg = f"Unsupported indicator: {name}"
    raise ValueError(msg)


def _validate_ohlcv_frame(name: str, frame: Any) -> None:
    if frame.empty:
        msg = f"Cannot compute {name}: empty OHLCV frame"
        raise IndicatorComputationError(msg)
    required_columns = ("open", "high", "low", "close", "volume")
    missing = tuple(column for column in required_columns if column not in frame.columns)
    if missing:
        msg = f"Cannot compute {name}: missing required OHLCV columns: {', '.join(missing)}"
        raise IndicatorComputationError(msg)


def _empty_output_frame(frame: Any, outputs: tuple[str, ...]) -> Any:
    output_frame = frame.copy()
    for output in outputs:
        output_frame[output] = import_module("pandas").NA
    return output_frame


def compute_indicator_series(
    name: str,
    frame: IndicatorFrame,
    *,
    parameters: dict[str, object] | None = None,
) -> IndicatorResult:
    normalized = normalize_indicator_parameters(name, parameters)
    if _is_pandas_frame(frame):
        return _compute_pandas_indicator(name, frame, normalized)
    if name == "rsi":
        close = frame["close"]
        rolling = close.rolling(_parameter_value(normalized, "length"))
        series = rolling.mean() if hasattr(rolling, "mean") else rolling
        return _result(name, ("rsi",), frame.assign(rsi=series))
    if name == "ema":
        close = frame["close"]
        series = close.ewm(span=_parameter_value(normalized, "length"), adjust=False).mean()
        return _result(name, ("ema",), frame.assign(ema=series))
    if name == "macd":
        close = frame["close"]
        fast = _parameter_value(normalized, "fastperiod")
        slow = _parameter_value(normalized, "slowperiod")
        signal = _parameter_value(normalized, "signalperiod")
        fast_series = close.ewm(span=fast, adjust=False).mean()
        slow_series = close.ewm(span=slow, adjust=False).mean()
        macd = fast_series - slow_series
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return _result(
            name,
            ("macd", "macd_signal", "macd_hist"),
            frame.assign(macd=macd, macd_signal=signal_line, macd_hist=histogram),
        )
    msg = f"Unsupported indicator: {name}"
    raise ValueError(msg)


def compute_indicator_batch(names: Iterable[str], frame: IndicatorFrame) -> list[IndicatorResult]:
    return [compute_indicator_series(name, frame) for name in names]
