# Proposal: Fix DuckDB Path Inconsistency & Rebuild Multi-Timeframe OHLCV

**Status**: Draft
**Date**: 2026-07-04
**Change**: `fix-duckdb-path`

## Problem Statement

The project has **three DuckDB files** in different locations, each used by different tools:

| Path | Size | Used By | State |
|------|------|---------|-------|
| `./data/ticks.duckdb` | 3.5 GB | Previous dbt runs | Has 153M raw ticks + `ohlcv_15s` (450K rows) |
| `./backend/data/ticks.duckdb` | 268 KB | API (`settings.duckdb_path`) | Empty — `dt_tick_data` with 0 rows |
| `./analytics/data/ticks.duckdb` | ✗ Deleted | Last `dbt build` | Was empty, no longer exists |

The root cause is that the relative path `data/ticks.duckdb` resolves differently depending on the working directory:
- API resolves from `backend/` → `backend/data/ticks.duckdb`
- dbt resolves from `analytics/` → `analytics/data/ticks.duckdb`
- Scripts may resolve from repo root → `./data/ticks.duckdb`

Additionally, the multi-timeframe OHLCV models (`ohlcv_1m` through `ohlcv_1d`) were added in PR #4 but **never materialized against a database with real data** — the dbt run that created them targeted an empty/temporary DuckDB file.

## Current State Gap

1. **API returns no data** — points to an empty DuckDB, so any query returns 0 results
2. **dbt models point to the wrong file** — `dbt build` creates/updates a file that nobody reads
3. **Multi-timeframe tables don't exist** — `ohlcv_1m`, `ohlcv_3m`, ..., `ohlcv_1d` are defined as dbt models but have never been populated with real tick data
4. **Dead DuckDB file** — `backend/data/ticks.duckdb` is a 268 KB waste that should be removed

## Proposed Solution

### 1. Unify DuckDB Path

Make `./data/ticks.duckdb` (repo root) the single canonical DuckDB file. Change every configuration and script that references a DuckDB path to point to this file using a consistent resolution strategy.

**Resolution strategy**: use an absolute path derived from the repo root at runtime, or make `data/ticks.duckdb` relative to the repo root and ensure all tools run from that root.

### 2. Rebuild Multi-Timeframe Tables

Run `dbt run --full-refresh` against the canonical DuckDB file to materialize all 8 timeframe tables (`ohlcv_1m` through `ohlcv_1d`) with real data derived from the existing 450K `ohlcv_15s` rows.

### 3. Clean Up Dead File

Remove `backend/data/ticks.duckdb` after confirming the API successfully reads from the canonical file.

## Scope

### In Scope
- `backend/src/funding_backtester/config.py` — `duckdb_path` resolution
- `analytics/profiles.yml` — DuckDB path for dbt
- `backend/src/funding_backtester/scripts/load_ticks.py` — if it references a DuckDB path
- Any other file with hardcoded DuckDB path (search the codebase)
- Run `dbt run --full-refresh` to populate multi-timeframe tables
- Remove `backend/data/ticks.duckdb`
- Update tests that reference DuckDB paths

### Out of Scope
- Changing the DuckDB storage engine or schema design
- Adding new timeframes beyond the 8 already defined
- Frontend changes
- CI/CD pipeline changes

## Success Criteria

1. `settings.duckdb_path` resolves to the canonical file (verified via Python)
2. `dbt run --full-refresh` completes successfully against the canonical file
3. All 9 `ohlcv_*` tables exist in the canonical DuckDB with correct row counts
4. API `/api/v1/ohlcv` returns data for all granularities
5. `backend/data/ticks.duckdb` is removed
6. All existing tests pass

## Next

→ Spec + Design phases
