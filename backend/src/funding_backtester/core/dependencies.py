"""Shared FastAPI dependencies."""

from funding_backtester.database import get_session

__all__ = ["get_session"]
