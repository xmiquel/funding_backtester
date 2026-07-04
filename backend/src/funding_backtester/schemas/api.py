"""API response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health endpoint response."""

    status: str


class RootResponse(BaseModel):
    """Root endpoint response."""

    message: str


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
