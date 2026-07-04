# Proposal: 15-Second OHLCV Aggregation Pipeline

## Intent

Reduce 153M tick rows (~3 TB scan) to manageable OHLCV bars for backtesting. Current tick-level queries are too slow for strategy testing — a 15s aggregation cuts row count by ~99.9% while preserving OHLCV structure for last-traded, bid, and ask prices.

## Scope

### In Scope
- dbt incremental model `ohlcv_15s` aggregating from `dt_tick_data`
- FastAPI endpoint `/api/v1/ohlcv` with symbol + date range query params
- Pydantic response schema for OHLCV bars
- DuckDB incremental materialization with `unique_key = (datetime, symbol)`

### Out of Scope
- Tick-level API endpoint (deferred)
- Real-time/live aggregation (deferred)
- Frontend UI for OHLCV charts
- Backfill of data older than `dt_tick_data` coverage

## Capabilities

### New Capabilities
- `ohlcv-aggregation`: 15-second OHLCV bar computation, storage, and REST query over tick data

### Modified Capabilities
- None (purely additive pipeline stage)

## Approach

1. **dbt model**: `analytics/models/marts/ohlcv_15s.sql` with incremental materialization. Window functions pick open/high/low/close per 15s bucket. Bucket via `date_trunc('second', event_ts) - INTERVAL (EXTRACT(SECOND FROM event_ts) % 15) SECOND`, stored as `datetime TIMESTAMP` with **second precision** (no fractional seconds).
2. **Incremental filter**: `datetime > COALESCE((SELECT MAX(datetime) FROM {{ this }}), '2000-01-01')` inside `{% if is_incremental() %}` block.
3. **API**: New router `backend/src/funding_backtester/api/v1/ohlcv.py`. Query params: `symbol` (required), `start_date`, `end_date`. Response: list of OHLCV bar Pydantic models.
4. **DuckDB sync bridge**: FastAPI queries `data/ticks.duckdb` via DuckDB Python API wrapped in `run_in_executor`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `analytics/models/marts/ohlcv_15s.sql` | New | Incremental dbt model |
| `backend/src/funding_backtester/api/v1/ohlcv.py` | New | OHLCV query endpoint |
| `backend/src/funding_backtester/schemas/api.py` | Modified | Add OHLCVBar schema |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Window-function boundary at 15s bucket edges | Med | Validate 1K-row sample against manual calc |
| Incremental miss if `dt_tick_data` stale | Low | Document `dbt build` ordering |
| DuckDB sync API in async FastAPI | Low | `run_in_executor` isolates blocking call |

## Rollback Plan

1. Drop `ohlcv_15s` from DuckDB
2. Remove `ohlcv.py` router and `OHLCVBar` schema
3. Remove model file from dbt project

## Dependencies

- `dt_tick_data` mart must exist and be refreshed before `ohlcv_15s` builds

## Success Criteria

- [ ] 15s OHLCV for MNQ0626 on 2026-03-15 matches manual SQL window calculation (spot-check 10 bars)
- [ ] `/api/v1/ohlcv?symbol=MNQ0626&start_date=2026-03-15&end_date=2026-03-16` returns bars in < 500ms
- [ ] Incremental build confirms row count delta equals new buckets only
