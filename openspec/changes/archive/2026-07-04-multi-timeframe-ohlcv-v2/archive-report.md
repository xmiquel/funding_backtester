# Archive Report: Multi-Timeframe OHLCV (v2)

**Date**: 2026-07-04
**Change**: multi-timeframe-ohlcv
**Status**: Archived — SDD cycle complete (PR #4 merged)

## Summary

Extend OHLCV from 15s-only to 8 coarse granularities (1m/3m/5m/15m/1h/3h/4h/1d) for backtesting queries. Implemented via a single dbt macro, 8 incremental dbt models, and an API `?granularity=` parameter with validated allow-list. Merged as PR #4.

## Open Items (Discovered After Merge)

The dbt models ran successfully but targeted a **different DuckDB file** than the API uses:
- dbt wrote to a temp file at `analytics/data/ticks.duckdb` (now deleted)
- The 3.5 GB real database at `data/ticks.duckdb` was not updated
- The API points to `backend/data/ticks.duckdb` (empty)

These issues are tracked in the next SDD change: `fix-duckdb-path`.

## Artifacts

| Artifact | Path |
|----------|------|
| Proposal | `openspec/changes/archive/2026-07-04-multi-timeframe-ohlcv-v2/proposal.md` |
| Spec | `openspec/changes/archive/2026-07-04-multi-timeframe-ohlcv-v2/specs/ohlcv-aggregation/spec.md` |
| Design | `openspec/changes/archive/2026-07-04-multi-timeframe-ohlcv-v2/design.md` |
| Tasks | `openspec/changes/archive/2026-07-04-multi-timeframe-ohlcv-v2/tasks.md` |

## Files Changed

See commit `9ee9bd7` (PR #4) for the full diff.

## Next Steps

Proceed with `fix-duckdb-path` to resolve the DuckDB file inconsistency and rebuild multi-timeframe tables with real tick data.
