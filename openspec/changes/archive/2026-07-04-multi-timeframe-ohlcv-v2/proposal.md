# Proposal: Multi-Timeframe OHLCV

## Intent

Extend OHLCV from 15s-only to 1m/3m/5m/15m/1h/3h/4h/1d so backtesting queries any granularity without tick recompute.

## Scope

### In Scope
- 8 incremental dbt models (1m → 1d) chained from ohlcv_15s
- 1 dbt macro to DRY the aggregation formula
- `?granularity=` param on existing `/ohlcv` endpoint
- Expanded tests via parametrized fixtures

### Out of Scope
- Custom sub-minute granularities (2s, 10s, 30s)
- Real-time streaming or UI granularity selector

## Capabilities

### Modified Capabilities
- `ohlcv-aggregation`: Multi-granularity — new models, API param, schema unchanged

## Approach

**dbt**: 8 thin files + 1 macro `ohlcv_aggregate(seconds)`. Each model calls the macro with its bucket size. Coarse models SELECT from `ohlcv_15s` (not raw ticks) — resample via `date_trunc` + window functions. Chain: `dt_tick_data → ohlcv_15s → ohlcv_{1m|...|1d}`. Macro wins over 8 copies: DRY logic + explicit lineage + per-model config.

**API**: Add `?granularity=15s` (default for backward compat) to `GET /api/v1/ohlcv`. Endpoint maps param → table name via validated allow-list. Single endpoint wins over 8: one discovery URL, no routing changes, zero schema breakage.

**Schema**: `OHLCVBar` unchanged — granularity is a request concern, not a data attribute. Adding it breaks existing clients for no gain.

**Incremental**: Each coarse model filters `WHERE bucket_dt > (SELECT MAX(bucket_dt) FROM this) - INTERVAL <2×bucket_seconds>` to handle boundary overlaps. The 15s model keeps its existing incremental logic.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `analytics/macros/ohlcv_aggregate.sql` | New | Shared aggregation macro |
| `analytics/models/marts/ohlcv_*.sql` | +8 files | 1m/3m/5m/15m/1h/3h/4h/1d models |
| `analytics/models/marts/schema.yml` | +8 entries | Model docs + column tests |
| `backend/.../api/v1/ohlcv.py` | Modified | Add granularity param, dynamic table |
| `backend/.../schemas/api.py` | Unchanged | OHLCVBar stays same |
| `backend/tests/test_ohlcv.py` | Expanded | Parametrized granularity tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Boundary gaps on partial builds | Low | 2× granularity lookback window |
| API param → table injection | Low | Validated allow-list |
| Test duplication | Low | Single parametrized fixture |

## Rollback Plan

(1) Remove new dbt models + macro. (2) Drop `granularity` param. (3) Rebuild `ohlcv_15s`. Zero data loss — coarse models are derived, no source data changed.

## Dependencies

- `ohlcv_15s` has data (existing)

## Success Criteria

- [ ] `dbt build` produces all 8 tables with row counts proportional to bucket size
- [ ] `GET /api/v1/ohlcv?symbol=X&granularity=1m` returns valid 15-field bars at 1m intervals
- [ ] `GET /api/v1/ohlcv?symbol=X` (no param) returns identical results to current — full backward compat
- [ ] All models survive `dbt build --full-refresh`
- [ ] Tests cover 15s + at least one coarse granularity with same OHLCV assertions