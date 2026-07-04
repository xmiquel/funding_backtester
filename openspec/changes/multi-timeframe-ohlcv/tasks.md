# Tasks: Multi-Timeframe OHLCV

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~360 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-forecast (→ single-pr) |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | dbt macro + 8 model files + schema.yml updates | PR 1 | Standalone dbt layer; verify via `dbt compile` |
| 2 | API granularity param | PR 1 | Dynamic table mapping with validated allow-list |
| 3 | Test expansion: conftest fixtures + parametrized tests | PR 1 | Verify spec scenarios; tests with code per commit |

## Phase 1: Foundation — dbt Macro & Models

- [x] 1.1 Create `analytics/macros/` dir + `analytics/macros/ohlcv_aggregate.sql` — bucket alignment, window functions, 2× lookback, sub-daily + daily modes
- [x] 1.2 Create `analytics/models/marts/ohlcv_1m.sql` — incremental, unique_key=(datetime,symbol), calls macro(bucket_seconds=60)
- [x] 1.3 Create `analytics/models/marts/ohlcv_3m.sql` — incremental, 180s bucket
- [x] 1.4 Create `analytics/models/marts/ohlcv_5m.sql` — incremental, 300s bucket
- [x] 1.5 Create `analytics/models/marts/ohlcv_15m.sql` — incremental, 900s bucket
- [x] 1.6 Create `analytics/models/marts/ohlcv_1h.sql` — incremental, 3600s bucket
- [x] 1.7 Create `analytics/models/marts/ohlcv_3h.sql` — incremental, 10800s bucket
- [x] 1.8 Create `analytics/models/marts/ohlcv_4h.sql` — incremental, 14400s bucket
- [x] 1.9 Create `analytics/models/marts/ohlcv_1d.sql` — incremental, is_daily=true, date_trunc alignment
- [x] 1.10 Add 8 model entries to `analytics/models/marts/schema.yml` — column tests, data_type, descriptions

## Phase 2: API Granularity

- [x] 2.1 Add `granularity` Query param (default `"15s"`) to `GET /api/v1/ohlcv` — `VALID_GRANULARITIES` allow-list, dynamic table name mapping, invalid → 422

## Phase 3: Tests

- [x] 3.1 Expand `ohlcv_db_path` fixture in `backend/tests/conftest.py` — create coarse granularity tables derived from 15s data via macro SQL patterns
- [x] 3.2 Add `TestMultiTimeframeBucketAlignment` + `TestMultiTimeframeAggregation` — parametrized tests for 1m/5m/1h/1d, OHLCV monotonicity, boundary overlap coverage
- [x] 3.3 Add backward compat test (no param → 15s identical) + invalid granularity → 422 + multi-symbol filtering with granularity
