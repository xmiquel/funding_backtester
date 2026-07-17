"""Public contracts, signal generation, and deterministic execution for backtests."""

from funding_backtester.backtesting.contracts import (
    BacktestConfig,
    BacktestFill,
    BacktestMetadata,
    BacktestResult,
    BacktestResultValidationError,
    BacktestRunSummary,
    BacktestTrade,
    BacktestValidationError,
    validate_backtest_result,
)
from funding_backtester.backtesting.engine import execute_next_bar_open
from funding_backtester.backtesting.strategy import build_signal_frame

__all__ = [
    "BacktestConfig",
    "BacktestFill",
    "BacktestMetadata",
    "BacktestResult",
    "BacktestResultValidationError",
    "BacktestRunSummary",
    "BacktestTrade",
    "BacktestValidationError",
    "build_signal_frame",
    "execute_next_bar_open",
    "validate_backtest_result",
]
