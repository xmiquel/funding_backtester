# Spec: DuckDB Path Unification & Multi-Timeframe Rebuild

**Status**: Draft
**Date**: 2026-07-04
**Change**: `fix-duckdb-path`
**Domain**: infrastructure

## Requirements

### R1: Canonical DuckDB Path

**ID**: R1
**Priority**: HIGH
**Description**: The project must have a single canonical DuckDB file at `./data/ticks.duckdb` (repo root). All tools, services, and scripts must resolve to this same file.

**Acceptance Criteria**:
- AC1.1: `funding_backtester.config.Settings.duckdb_path` resolves to an absolute path pointing to `<repo_root>/data/ticks.duckdb`
- AC1.2: `analytics/profiles.yml` DuckDB path resolves to the same `<repo_root>/data/ticks.duckdb` file
- AC1.3: `analytics/profiles.yml` does NOT use a relative path that changes meaning based on working directory
- AC1.4: Any script in `backend/src/funding_backtester/scripts/` that writes/reads a DuckDB file uses the canonical path
- AC1.5: No other `.duckdb` files are created outside the canonical path during normal operation

### R2: Multi-Timeframe Table Population

**ID**: R2
**Priority**: HIGH
**Description**: All 8 multi-timeframe OHLCV tables (`ohlcv_1m`, `ohlcv_3m`, `ohlcv_5m`, `ohlcv_15m`, `ohlcv_1h`, `ohlcv_3h`, `ohlcv_4h`, `ohlcv_1d`) must be materialized in the canonical DuckDB with data derived from the existing `ohlcv_15s` table (450K rows).

**Acceptance Criteria**:
- AC2.1: `dbt run --full-refresh` completes successfully against the canonical DuckDB
- AC2.2: All 8 timeframe tables exist in the `main` schema of the canonical DuckDB
- AC2.3: Each timeframe table has non-zero row count
- AC2.4: Testing through the API endpoint `GET /api/v1/ohlcv?symbol=ES0626&granularity=1m` returns data
- AC2.5: Existing `dbt test` suite passes (not_null constraints, uniqueness)

### R3: Clean Up Orphan DuckDB Files

**ID**: R3
**Priority**: MEDIUM
**Description**: Remove `backend/data/ticks.duckdb` once the API reads from the canonical file. No stale empty DuckDB files should remain.

**Acceptance Criteria**:
- AC3.1: `backend/data/ticks.duckdb` is deleted
- AC3.2: No test or script references the old path `backend/data/ticks.duckdb`

### R4: Backward Compatibility

**ID**: R4
**Priority**: HIGH
**Description**: The existing API behavior must be preserved. No breaking changes to the API contract.

**Acceptance Criteria**:
- AC4.1: `GET /api/v1/ohlcv?symbol=ES0626` (default granularity `15s`) returns correct 15s OHLCV data
- AC4.2: All existing tests in `tests/test_ohlcv.py` pass without modification
- AC4.3: All existing dbt tests pass

## Files to Change

| File | Action | Why |
|------|--------|-----|
| `backend/src/funding_backtester/config.py` | Modify | `duckdb_path` must resolve to repo-root canonical file |
| `analytics/profiles.yml` | Modify | DuckDB path must use absolute path or repo-root-relative |
| `backend/src/funding_backtester/scripts/load_ticks.py` | Check+Modify | May reference DuckDB path; align to canonical |
| `backend/data/ticks.duckdb` | Delete | Orphan empty file |
| `.env` (if exists) | Check | `duckdb_path` env var override |

## Non-Goals

- Schema changes to any OHLCV table
- New timeframes beyond the 8 already defined
- Performance tuning of DuckDB queries
- CI/CD pipeline changes
- Frontend changes
