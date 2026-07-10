"""Compatibility exports for the bounded indicator parameter catalog."""

from funding_backtester.indicators.parameters import (
    INDICATOR_CATALOG,
    IndicatorDefinition,
    canonical_parameter_json,
    feature_id,
    get_indicator_definition,
    normalize_indicator_parameters,
    parameter_hash,
)

__all__ = [
    "INDICATOR_CATALOG",
    "IndicatorDefinition",
    "canonical_parameter_json",
    "feature_id",
    "get_indicator_definition",
    "normalize_indicator_parameters",
    "parameter_hash",
]
