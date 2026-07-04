# Archive Report: Fix DuckDB Path Inconsistency

**Date**: 2026-07-04
**Change**: fix-duckdb-path
**Status**: Archived — SDD cycle complete

## Summary

Fixed the DuckDB path inconsistency where API, dbt, and scripts pointed to different DuckDB files. Unified everything to the canonical `./data/ticks.duckdb` (3.5 GB) at the repo root. Rebuilt all 8 multi-timeframe OHLCV tables with real tick data. Removed the orphan empty DuckDB file at `backend/data/`.

## What Was Done

- Created `backend/src/funding_backtester/_paths.py` — `_find_repo_root()` utility using `.git` + `backend/pyproject.toml` markers
- Modified `backend/src/funding_backtester/config.py` — `duckdb_path` resolves to `<repo_root>/data/ticks.duckdb`
- Modified `analytics/profiles.yml` — path changed to `../data/ticks.duckdb`
- Modified `backend/src/funding_backtester/scripts/load_ticks.py` — uses canonical path from config
- Ran `dbt run --full-refresh` — populated all 9 `ohlcv_*` tables with real data (103 to 450K rows)
- Deleted `backend/data/ticks.duckdb` (274 KB, empty)
- Added `tests/test_paths.py` — 7 tests for repo root resolution

## Artifacts

| Artifact | Path |
|----------|------|
| Proposal | `openspec/changes/archive/2026-07-04-fix-duckdb-path/proposal.md` |
| Spec | `openspec/changes/archive/2026-07-04-fix-duckdb-path/specs/duckdb-path/spec.md` |
| Design | `openspec/changes/archive/2026-07-04-fix-duckdb-path/design.md` |
| Tasks | `openspec/changes/archive/2026-07-04-fix-duckdb-path/tasks.md` |
| Apply Progress | `openspec/changes/archive/2026-07-04-fix-duckdb-path/apply-progress.md` |
| Verify Report | `openspec/changes/archive/2026-07-04-fix-duckdb-path/verify-report.md` |

## Verification Results

- **Verdict**: PASS
- **Tests**: 84/84 passed (incl. 7 new path tests)
- **dbt tests**: 37 passed
- **API smoke test**: All 9 granularities return real data
- **Spec compliance**: 15/15 ACs PASS

## Files Changed

| File | Action |
|------|--------|
| `backend/src/funding_backtester/_paths.py` | Created |
| `backend/tests/test_paths.py` | Created |
| `backend/src/funding_backtester/config.py` | Modified |
| `analytics/profiles.yml` | Modified |
| `backend/src/funding_backtester/scripts/load_ticks.py` | Modified |
| `backend/data/ticks.duckdb` | Deleted |

## Remaining Risks

| Risk | Severity | Notes |
|------|----------|-------|
| `profiles.yml` relative path breaks if `analytics/` moves | Low | Env var `DBT_DUCKDB_PATH` available as override |
| Leftover `ohlcv_15s__dbt_backup` table | Low | Normal dbt artifact from `--full-refresh`; ignored by API |
