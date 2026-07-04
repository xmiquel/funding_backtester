# Apply Progress: Fix DuckDB Path Inconsistency

**Change**: `fix-duckdb-path`
**Date**: 2026-07-04
**Status**: Complete

## Structured Status

| Field | Value |
|-------|-------|
| applyState | complete |
| nextRecommended | verify |
| phase | apply |
| actionContext.mode | implementation |
| allowedEditRoots | repo root |

## TDD Cycle Evidence

| Step | Action | Result |
|------|--------|--------|
| RED | Wrote `tests/test_paths.py` with 7 tests | `ModuleNotFoundError` for `funding_backtester._paths` |
| GREEN | Created `_paths.py` with `_find_repo_root()` + `duckdb_path()` | 7/7 passed |
| REFACTOR | Changed marker from `pyproject.toml` to `.git` + `backend/pyproject.toml` (actual root has no pyproject.toml) | 7/7 passed |
| VERIFY | Updated `config.py` → verified path resolves | `<repo_root>/data/ticks.duckdb` |
| VERIFY | Updated `profiles.yml` | dbt uses `../data/ticks.duckdb` |
| VERIFY | Updated `load_ticks.py` | Uses `settings.duckdb_path` as default |
| VERIFY | `dbt run --full-refresh` | 12 models, all PASS (116s) |
| VERIFY | `dbt test` | 37 data tests, all PASS (20s) |
| VERIFY | Table verification | All 9 ohlcv tables: 103–450K rows; dt_tick_data: 153M rows |
| VERIFY | Deleted `backend/data/ticks.duckdb` | Removed 274 KB orphan |
| VERIFY | `uv run pytest` | 84 tests, all PASS |
| VERIFY | API smoke test | MNQ0626 returns 357K (15s), 90K (1m), 80 (1d), 1.5K (1h) bars |

## Files Changed

| File | Action | Notes |
|------|--------|-------|
| `backend/src/funding_backtester/_paths.py` | **Created** | `_find_repo_root()` + `duckdb_path()` |
| `backend/tests/test_paths.py` | **Created** | 7 tests covering repo root + duckdb path |
| `backend/src/funding_backtester/config.py` | Modified | `duckdb_path` default → `str(_find_repo_root() / "data" / "ticks.duckdb")` |
| `analytics/profiles.yml` | Modified | Default path → `../data/ticks.duckdb` |
| `backend/src/funding_backtester/scripts/load_ticks.py` | Modified | `--duckdb-path` default → `settings.duckdb_path` |
| `backend/data/ticks.duckdb` | **Deleted** | 274 KB orphan empty file |

## Deviations from Design

1. **Marker strategy changed**: The design specified `pyproject.toml` as repo root marker, but `pyproject.toml` only exists in `backend/`, not at repo root. Changed to detect both `.git/` + `backend/pyproject.toml` for reliable root identification.

## Verification Evidence

- Config path: `<repo_root>/data/ticks.duckdb` ✅
- dbt run: 12/12 models PASS ✅
- dbt test: 37/37 tests PASS ✅
- Backend tests: 84/84 PASS ✅
- API: Returns data for MNQ0626 at all granularities ✅
- Orphan `backend/data/ticks.duckdb`: Deleted ✅

## Remaining Tasks

None. All tasks completed.

## Workload / PR Boundary

- Estimated changed lines: ~100 (40 code + 60 tests/documentation)
- 400-line budget risk: Low
- Delivery: Single PR
