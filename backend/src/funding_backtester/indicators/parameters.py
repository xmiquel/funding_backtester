"""Bounded indicator parameter catalog and deterministic feature identity."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndicatorDefinition:
    name: str
    library: str
    parameters: dict[str, object]
    outputs: tuple[str, ...]
    min_lookback: int


INDICATOR_CATALOG: dict[str, IndicatorDefinition] = {
    "sma": IndicatorDefinition("sma", "pandas_ta_classic", {"length": 20}, ("sma",), 20),
    "ema": IndicatorDefinition("ema", "pandas_ta_classic", {"length": 21}, ("ema",), 21),
    "rsi": IndicatorDefinition("rsi", "pandas_ta_classic", {"length": 14}, ("rsi",), 14),
    "macd": IndicatorDefinition(
        "macd",
        "talib",
        {"fastperiod": 12, "slowperiod": 26, "signalperiod": 9},
        ("macd", "macd_signal", "macd_hist"),
        34,
    ),
    "atr": IndicatorDefinition(
        "atr",
        "pandas_ta_classic",
        {"length": 14},
        ("atr",),
        14,
    ),
    "bbands": IndicatorDefinition(
        "bbands",
        "pandas_ta_classic",
        {"length": 20, "std": 2},
        ("bbands_lower", "bbands_middle", "bbands_upper"),
        20,
    ),
}


def get_indicator_definition(name: str) -> IndicatorDefinition:
    try:
        return INDICATOR_CATALOG[name]
    except KeyError as exc:
        msg = f"Unsupported indicator: {name}"
        raise ValueError(msg) from exc


def normalize_indicator_parameters(
    name: str, parameters: dict[str, object] | None = None
) -> dict[str, object]:
    definition = get_indicator_definition(name)
    expected = definition.parameters
    requested = expected if parameters is None else parameters
    if requested != expected:
        msg = (
            f"Unsupported parameters for {name}: expected "
            f"{canonical_parameter_json(expected)} got {canonical_parameter_json(requested)}"
        )
        raise ValueError(msg)
    return dict(expected)


def canonical_parameter_json(parameters: dict[str, object]) -> str:
    return json.dumps(parameters, sort_keys=True, separators=(",", ":"))


def parameter_hash(parameters: dict[str, object]) -> str:
    return hashlib.sha256(canonical_parameter_json(parameters).encode("utf-8")).hexdigest()


def feature_id(
    *,
    source_model: str,
    symbol: str,
    timeframe: str,
    feature_name: str,
    parameters: dict[str, object],
    computation_version: str,
) -> str:
    identity = "|".join(
        (
            source_model,
            symbol,
            timeframe,
            feature_name,
            canonical_parameter_json(parameters),
            computation_version,
        )
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()
