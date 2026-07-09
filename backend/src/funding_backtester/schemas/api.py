"""API response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str


class RootResponse(BaseModel):
    """Root endpoint response."""

    message: str


class ValidationErrorDetail(BaseModel):
    """A single validation error item matching FastAPI/Pydantic convention."""

    type: str
    loc: tuple[str | int, ...]
    msg: str
    input: str | None = None


class ValidationErrorResponse(BaseModel):
    """Consistent validation error response wrapper."""

    detail: list[ValidationErrorDetail]


class OHLCVBar(BaseModel):
    """15-second OHLCV bar with bid/ask mirrors."""

    datetime: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    bid_open: float
    bid_high: float
    bid_low: float
    bid_close: float
    ask_open: float
    ask_high: float
    ask_low: float
    ask_close: float

    model_config = ConfigDict(from_attributes=True)


class FeatureCatalogEntry(BaseModel):
    """Catalog entry for a bounded indicator feature."""

    name: str
    library: str
    parameters: dict[str, object]
    outputs: list[str]
    min_lookback: int


class FeatureMetaResponse(BaseModel):
    """Available feature metadata from persisted tables."""

    symbols: list[str]
    timeframes: list[str]
    source_models: list[str]


class FeatureRow(BaseModel):
    """Persisted feature row returned by the features API."""

    datetime: datetime
    symbol: str
    timeframe: str
    source_model: str
    feature_name: str
    feature_id: str
    parameter_hash: str
    parameter_json: str
    output_name: str
    value: float | None
    computed_at: datetime
    computation_version: str
    pandas_ta_classic_version: str
    talib_available: bool
    talib_version: str | None
    talib_used: bool

    model_config = ConfigDict(from_attributes=True)
