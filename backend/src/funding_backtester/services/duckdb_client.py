"""Read-only DuckDB client with async bridge for FastAPI."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import duckdb

_executor = ThreadPoolExecutor(max_workers=1)


class DuckDBClient:
    """Read-only DuckDB connection manager for OHLCV queries.

    Uses a single dedicated connection and wraps blocking calls in
    ``run_in_executor`` for async FastAPI compatibility.
    """

    def __init__(self, db_path: str) -> None:
        self._conn = duckdb.connect(db_path, read_only=True)

    async def query(self, sql: str, params: list[object] | None = None) -> list[tuple[object, ...]]:
        """Execute a read-only SQL query asynchronously.

        Args:
            sql: SQL query string with ``?`` placeholders.
            params: List of parameter values for placeholders.

        Returns:
            List of result rows as tuples.
        """
        return await asyncio.get_event_loop().run_in_executor(
            _executor, self._sync_query, sql, params
        )

    def _sync_query(self, sql: str, params: list[object] | None) -> list[tuple[object, ...]]:
        return self._conn.execute(sql, params or []).fetchall()

    def close(self) -> None:
        """Close the underlying DuckDB connection."""
        self._conn.close()
