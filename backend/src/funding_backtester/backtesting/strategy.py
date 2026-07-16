from __future__ import annotations

import pandas as pd

from funding_backtester.backtesting.contracts import BacktestValidationError, validate_window_pair


def _validate_temporal_index(close: pd.Series) -> None:
    if not isinstance(close, pd.Series):
        raise BacktestValidationError("close must be a pandas Series")
    if close.empty:
        return
    if not isinstance(close.index, pd.DatetimeIndex):
        raise BacktestValidationError("close must use a DatetimeIndex")
    if not close.index.is_monotonic_increasing or not close.index.is_unique:
        raise BacktestValidationError("close index must be strictly increasing and unique")


def build_signal_frame(
    close: pd.Series,
    *,
    fast_window: int,
    slow_window: int,
) -> pd.DataFrame:
    _validate_temporal_index(close)
    validate_window_pair(fast_window, slow_window)

    frame = pd.DataFrame({"close": close.astype("float64")})
    frame["fast_ma"] = frame["close"].rolling(fast_window, min_periods=fast_window).mean()
    frame["slow_ma"] = frame["close"].rolling(slow_window, min_periods=slow_window).mean()
    frame["bullish_cross"] = (frame["fast_ma"] > frame["slow_ma"]) & (
        frame["fast_ma"].shift(1) <= frame["slow_ma"].shift(1)
    )
    frame["bearish_cross"] = (frame["fast_ma"] < frame["slow_ma"]) & (
        frame["fast_ma"].shift(1) >= frame["slow_ma"].shift(1)
    )
    return frame
