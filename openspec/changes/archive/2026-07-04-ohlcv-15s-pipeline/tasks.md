# Tasks: 15-Second OHLCV Aggregation Pipeline

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~250 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | single-pr |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

## Phase 1: dbt Model

- [x] 1.1 Create `analytics/models/marts/ohlcv_15s.sql` — incremental model with 15s bucket formula, OHLCV for last/bid/ask, `unique_key=(datetime,symbol)`
- [x] 1.2 Modify `analytics/models/marts/schema.yml` — add `ohlcv_15s` model entry with all 15 column definitions and `not_null` tests on `datetime`, `symbol`, `open`, `close`

## Phase 2: Backend Infrastructure

- [x] 2.1 Modify `backend/src/funding_backtester/config.py` — add `duckdb_path: str` field pointing to `data/ticks.duckdb`
- [x] 2.2 Create `backend/src/funding_backtester/services/__init__.py` — service package init
- [x] 2.3 Create `backend/src/funding_backtester/services/duckdb_client.py` — `DuckDBClient` read-only connection manager with `async query()` wrapping `run_in_executor`

## Phase 3: API Layer

- [x] 3.1 Modify `backend/src/funding_backtester/schemas/api.py` — add `OHLCVBar` Pydantic model with 15 fields (`datetime`, `symbol`, `open`–`close`, `volume`, `bid_*`, `ask_*`)
- [x] 3.2 Create `backend/src/funding_backtester/api/v1/ohlcv.py` — `GET /ohlcv` endpoint with `symbol` (required), `start_date`, `end_date` params; queries DuckDB via `DuckDBClient`, returns `list[OHLCVBar]`
- [x] 3.3 Modify `backend/src/funding_backtester/main.py` — import `ohlcv.router` and register with `app.include_router`

## Phase 4: Testing

- [x] 4.1 Add unit test for 15s bucket alignment — 5 edge-case timestamps against manual calc
- [x] 4.2 Add unit test for `OHLCVBar` — JSON round-trip, null handling, type coercion
- [x] 4.3 Add integration test for dbt model — build `ohlcv_15s` with 100 known ticks, assert 15 OHLCV columns
- [x] 4.4 Add e2e test for `GET /api/v1/ohlcv` — httpx AsyncClient, test symbol-only, date-filtered, missing-symbol, empty-result
