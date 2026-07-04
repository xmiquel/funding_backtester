# Design: 15-Second OHLCV Aggregation Pipeline

## Technical Approach

Add a dbt incremental model (`ohlcv_15s`) above `dt_tick_data` that aggregates ticks into 15-second OHLCV bars, plus a FastAPI read-only endpoint backed by a DuckDB sync bridge. Purely additive — no existing models or endpoints change.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Aggregation method | `MIN`/`MAX` + first/last via `ROW_NUMBER` window functions | Window functions (`first_value`/`last_value`), aggregate `min_by`/`max_by` | `ROW_NUMBER` is more portable across DuckDB versions than `min_by`/`max_by` and avoids the `OVER` complexity of `first_value`/`last_value`. Grouped `MIN`/`MAX` with conditional `ROW_NUMBER` is the clearest DuckDB-compatible pattern. |
| dbt materialization | `incremental` with `unique_key=(datetime,symbol)` | `table` (full refresh) | 153M rows → ~200K rows/day; full rebuild is wasteful. Incremental handles backfill and daily runs. |
| DuckDB API bridge | Dedicated read-only connection in `run_in_executor` | Async DuckDB (unofficial), connection pool per request | DuckDB Python client is sync-only. `run_in_executor` is the standard FastAPI pattern for blocking I/O. Single read-only connection avoids locking contention with dbt writes. |
| API router placement | New `api/v1/ohlcv.py` module | Single large routes file | Follows existing `health.py` pattern — one module per resource. |
| Bucket formula | `date_trunc('second', ts) - INTERVAL (EXTRACT(SECOND FROM ts) % 15) SECOND` | `ts - INTERVAL (EXTRACT(EPOCH FROM ts)::BIGINT % 15) SECOND` | Both work identically. The `date_trunc` variant reads more idiomatically for timestamp manipulation. |

## Data Flow

```
NT8 .txt files
     │
     ▼
raw_ticks (DuckDB view, read_csv_auto)
     │
     ▼ dbt stg_tick_data (view)
     │
     ▼ dbt dt_tick_data (table, full refresh)
     │
     ▼ dbt ohlcv_15s (incremental, unique_key=(datetime,symbol))
     │
     ▼
DuckDB ──→ FastAPI /api/v1/ohlcv (sync bridge via run_in_executor)
               │
               └──→ JSON [OHLCVBar, ...]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `analytics/models/marts/ohlcv_15s.sql` | Create | dbt incremental model: bucket ticks → OHLCV per 15s window |
| `analytics/models/marts/schema.yml` | Modify | Add `ohlcv_15s` model with column definitions + tests |
| `backend/src/funding_backtester/services/__init__.py` | Create | Package init for services layer |
| `backend/src/funding_backtester/services/duckdb_client.py` | Create | Read-only DuckDB connection manager with `run_in_executor` query helper |
| `backend/src/funding_backtester/schemas/api.py` | Modify | Add `OHLCVBar` Pydantic model |
| `backend/src/funding_backtester/api/v1/ohlcv.py` | Create | `GET /api/v1/ohlcv` endpoint with query params |
| `backend/src/funding_backtester/main.py` | Modify | Register `ohlcv.router` |
| `backend/src/funding_backtester/config.py` | Modify | Add `duckdb_path` setting |

## Interfaces / Contracts

### OHLCVBar Schema (Pydantic)

```python
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

# Response: list[OHLCVBar]
```

### dbt Model (ohlcv_15s.sql)

```sql
{{ config(materialized='incremental', unique_key=['datetime', 'symbol']) }}

WITH bucketed AS (
    SELECT
        date_trunc('second', event_ts)
          - INTERVAL (EXTRACT(SECOND FROM event_ts) % 15) SECOND AS datetime,
        symbol, last, bid, ask, volume,
        ROW_NUMBER() OVER (PARTITION BY symbol, datetime ORDER BY event_ts) AS rn_asc,
        ROW_NUMBER() OVER (PARTITION BY symbol, datetime ORDER BY event_ts DESC) AS rn_desc
    FROM {{ ref('dt_tick_data') }}
    {% if is_incremental() %}
    WHERE datetime > COALESCE((SELECT MAX(datetime) FROM {{ this }}), '2000-01-01')
    {% endif %}
)
SELECT
    datetime, symbol,
    MAX(CASE WHEN rn_asc = 1 THEN last END) AS open,
    MAX(last) AS high,
    MIN(last) AS low,
    MAX(CASE WHEN rn_desc = 1 THEN last END) AS close,
    SUM(volume) AS volume,
    MAX(CASE WHEN rn_asc = 1 THEN bid END) AS bid_open,
    MAX(bid) AS bid_high,
    MIN(bid) AS bid_low,
    MAX(CASE WHEN rn_desc = 1 THEN bid END) AS bid_close,
    MAX(CASE WHEN rn_asc = 1 THEN ask END) AS ask_open,
    MAX(ask) AS ask_high,
    MIN(ask) AS ask_low,
    MAX(CASE WHEN rn_desc = 1 THEN ask END) AS ask_close
FROM bucketed
GROUP BY datetime, symbol
```

### DuckDB Client

```python
import duckdb
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=1)

class DuckDBClient:
    def __init__(self, db_path: str):
        self._conn = duckdb.connect(db_path, read_only=True)

    async def query(self, sql: str, params: list | None = None) -> list[duckdb.DuckDBPyConnection]:
        return await asyncio.get_event_loop().run_in_executor(
            _executor, self._sync_query, sql, params
        )

    def _sync_query(self, sql: str, params: list | None) -> list:
        return self._conn.execute(sql, params or []).fetchall()
```

### DuckDB Query

```sql
SELECT datetime, symbol, open, high, low, close, volume,
       bid_open, bid_high, bid_low, bid_close,
       ask_open, ask_high, ask_low, ask_close
FROM ohlcv_15s
WHERE symbol = ?              -- required
  AND datetime >= ?           -- start_date (optional, default '1970-01-01')
  AND datetime <  ?           -- end_date + 1 day (optional, default '2099-12-31')
ORDER BY datetime ASC
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Bucket alignment formula | Test 5 edge-case timestamps (exact boundary, near end, ms precision) against manual calc |
| Unit | `OHLCVBar` Pydantic model | JSON serialization round-trip, validation of null/missing fields |
| Integration | dbt model against DuckDB | Build model with 100 known ticks, assert 15 columns match expected bar values |
| Integration | Single-tick bucket | Open/high/low/close = same `last`, volume = tick volume |
| E2E | API endpoint | httpx `AsyncClient` hitting real endpoint against DuckDB with known data |

## Open Questions

- [ ] Should `volume` be `BIGINT` or `INTEGER` in Pydantic? Tick volumes are small but sum across 153M rows may exceed 32-bit.
- [ ] Connection lifecycle: open once at startup or lazy on first request? Startup aligns with lifespan but delays boot.
