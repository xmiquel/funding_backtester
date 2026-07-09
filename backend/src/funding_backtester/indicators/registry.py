"""Catalog-only indicator request registry."""

from __future__ import annotations

from dataclasses import dataclass

from funding_backtester.indicators.parameters import (
    INDICATOR_CATALOG,
    normalize_indicator_parameters,
)


@dataclass(frozen=True, slots=True)
class IndicatorRequest:
    name: str
    parameters: dict[str, object]
    outputs: tuple[str, ...]
    min_lookback: int


def validate_indicator_request(
    name: str, parameters: dict[str, object] | None = None
) -> IndicatorRequest:
    normalized = normalize_indicator_parameters(name, parameters)
    definition = INDICATOR_CATALOG[name]
    return IndicatorRequest(
        name=definition.name,
        parameters=normalized,
        outputs=definition.outputs,
        min_lookback=definition.min_lookback,
    )


def describe_indicator(name: str) -> IndicatorRequest:
    return validate_indicator_request(name)


def list_indicator_metadata() -> tuple[IndicatorRequest, ...]:
    return tuple(validate_indicator_request(name) for name in sorted(INDICATOR_CATALOG))
