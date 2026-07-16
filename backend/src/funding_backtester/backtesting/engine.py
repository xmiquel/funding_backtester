from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Literal

import pandas as pd

from funding_backtester.backtesting.contracts import (
    BacktestConfig,
    BacktestFill,
    BacktestMetadata,
    BacktestResult,
    BacktestRunSummary,
    BacktestTrade,
    BacktestValidationError,
)
from funding_backtester.backtesting.strategy import build_signal_frame

_BASIS_POINTS = Decimal("10000")


def _as_decimal(value: object, field_name: str) -> Decimal:
    try:
        converted = Decimal(str(value))
    except (ValueError, TypeError):
        raise BacktestValidationError(f"{field_name} must contain numeric values") from None
    if not converted.is_finite():
        raise BacktestValidationError(f"{field_name} must contain finite values")
    return converted


def _validate_open_prices(close: pd.Series, open_prices: pd.Series) -> None:
    if not isinstance(close, pd.Series):
        raise BacktestValidationError("close must be a pandas Series")
    if not isinstance(open_prices, pd.Series):
        raise BacktestValidationError("open_prices must be a pandas Series")
    if close.empty or open_prices.empty:
        raise BacktestValidationError("close and open_prices must be non-empty")
    if not open_prices.index.equals(close.index):
        raise BacktestValidationError("open_prices must use the same index as close")
    for value in open_prices:
        price = _as_decimal(value, "open_prices")
        if price < 0:
            raise BacktestValidationError("open_prices must contain non-negative values")


def _canonical_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, frozenset):
        canonical_items = (_canonical_value(item) for item in value)
        return sorted(
            canonical_items,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, Decimal):
        return str(value)
    return value


def _run_id(config: BacktestConfig, metadata: BacktestMetadata) -> str:
    payload = {
        "config": {
            "source_model": config.source_model,
            "symbol": config.symbol,
            "timeframe": config.timeframe,
            "fast_window": config.fast_window,
            "slow_window": config.slow_window,
            "commission_bps": config.commission_bps,
            "slippage_bps": config.slippage_bps,
            "initial_cash": config.initial_cash,
            "strategy_version": config.strategy_version,
            "schema_version": config.schema_version,
        },
        "metadata": {
            "input_snapshot_id": metadata.input_snapshot_id,
            "code_revision": metadata.code_revision,
            "parameters": metadata.parameters,
            "schema_version": metadata.schema_version,
        },
    }
    encoded = json.dumps(_canonical_value(payload), sort_keys=True, separators=(",", ":"))
    return f"run-{hashlib.sha256(encoded.encode()).hexdigest()[:16]}"


def execute_next_bar_open(
    close: pd.Series,
    open_prices: pd.Series,
    *,
    config: BacktestConfig,
    metadata: BacktestMetadata,
) -> BacktestResult:
    """Execute close signals at the next available bar open.

    Args:
        close: Ordered close prices indexed by unique, increasing timestamps.
        open_prices: Non-empty, non-negative, finite numeric opens with exactly the
            same timestamp index as ``close``.
        config: Validated windows and costs. Prices and costs are per one unit;
            commission and slippage rates are expressed in basis points.
        metadata: Validated reproducibility identifiers and canonical parameters.

    Returns:
        Immutable run summary, fills, completed trades, and signals that could not
        be filled because no next bar existed. Fill prices are Decimal price units;
        buys pay positive slippage and sells receive negative slippage. Commission
        is ``fill_price * commission_bps / 10000`` per one unit, and completed-trade
        PnL is the price difference less both commissions and slippages.

    The event loop is deliberately long-only: bullish crosses open a position and
    bearish crosses close it. A signal on the final bar is reported without a fill.
    A position still open at the end remains represented by its entry fill, is not
    synthetically closed, and is excluded from ``trades``.
    """
    _validate_open_prices(close, open_prices)
    signal_frame = build_signal_frame(
        close,
        fast_window=config.fast_window,
        slow_window=config.slow_window,
    )
    run_id = _run_id(config, metadata)
    commission_rate = config.commission_bps / _BASIS_POINTS
    slippage_rate = config.slippage_bps / _BASIS_POINTS
    fills: list[BacktestFill] = []
    trades: list[BacktestTrade] = []
    unfilled: list[tuple[Literal["buy", "sell"], datetime]] = []
    entry: tuple[datetime, Decimal, Decimal, Decimal] | None = None

    for index in range(len(signal_frame)):
        side: Literal["buy", "sell"] | None = None
        if bool(signal_frame.iloc[index]["bullish_cross"]) and entry is None:
            side = "buy"
        elif bool(signal_frame.iloc[index]["bearish_cross"]) and entry is not None:
            side = "sell"
        if side is None:
            continue

        signal_timestamp = signal_frame.index[index].to_pydatetime()
        if index + 1 >= len(signal_frame):
            unfilled.append((side, signal_timestamp))
            continue

        raw_price = _as_decimal(open_prices.iloc[index + 1], "open_prices")
        slippage = raw_price * slippage_rate
        fill_price = raw_price + slippage if side == "buy" else raw_price - slippage
        commission = fill_price * commission_rate
        fill_timestamp = signal_frame.index[index + 1].to_pydatetime()
        fills.append(
            BacktestFill(
                run_id=run_id,
                side=side,
                signal_timestamp=signal_timestamp,
                fill_timestamp=fill_timestamp,
                fill_price=fill_price,
                commission=commission,
                slippage=slippage,
            )
        )
        if side == "buy":
            entry = (fill_timestamp, raw_price, commission, slippage)
        else:
            if entry is None:
                raise BacktestValidationError(
                    "sell signal cannot be executed without an open position"
                )
            entry_timestamp, entry_raw_price, entry_commission, entry_slippage = entry
            trades.append(
                BacktestTrade(
                    run_id=run_id,
                    entry_timestamp=entry_timestamp,
                    exit_timestamp=fill_timestamp,
                    entry_price=entry_raw_price,
                    exit_price=raw_price,
                    commission=entry_commission + commission,
                    slippage=entry_slippage + slippage,
                    net_pnl=(raw_price - entry_raw_price)
                    - entry_commission
                    - commission
                    - entry_slippage
                    - slippage,
                )
            )
            entry = None

    summary = BacktestRunSummary(
        run_id=run_id,
        schema_version=config.schema_version,
        strategy_version=config.strategy_version,
        input_snapshot_id=metadata.input_snapshot_id,
        code_revision=metadata.code_revision,
        commission_bps=config.commission_bps,
        slippage_bps=config.slippage_bps,
        unfilled_signal_count=len(unfilled),
    )
    return BacktestResult(
        summary=summary,
        fills=tuple(fills),
        trades=tuple(trades),
        unfilled_signals=tuple(unfilled),
    )
