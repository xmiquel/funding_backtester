"""Indicator feature layer exports."""

from funding_backtester.indicators.duckdb_io import build_indicator_feature_stage
from funding_backtester.indicators.engine import (
    IndicatorResult,
    compute_indicator_batch,
    compute_indicator_series,
)
from funding_backtester.indicators.parameters import (
    INDICATOR_CATALOG,
    IndicatorDefinition,
    canonical_parameter_json,
    feature_id,
    parameter_hash,
)
from funding_backtester.indicators.registry import (
    IndicatorRequest,
    describe_indicator,
    list_indicator_metadata,
    validate_indicator_request,
)
from funding_backtester.indicators.vectorbt_loader import load_features

__all__ = [
    "INDICATOR_CATALOG",
    "IndicatorDefinition",
    "IndicatorRequest",
    "IndicatorResult",
    "canonical_parameter_json",
    "build_indicator_feature_stage",
    "compute_indicator_batch",
    "compute_indicator_series",
    "load_features",
    "describe_indicator",
    "feature_id",
    "list_indicator_metadata",
    "parameter_hash",
    "validate_indicator_request",
]
