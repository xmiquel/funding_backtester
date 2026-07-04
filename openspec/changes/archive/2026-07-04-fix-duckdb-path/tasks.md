# Tasks: Fix DuckDB Path Inconsistency & Rebuild Multi-Timeframe OHLCV

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~40 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | auto-forecast (→ single-pr) |

## Phase 1: Path Unification

- [x] 1.1 Create `backend/src/funding_backtester/_paths.py` — `_find_repo_root()` utility with `.git` + `backend/pyproject.toml` marker detection
- [x] 1.2 Modify `backend/src/funding_backtester/config.py` — update `duckdb_path` default to `str(_find_repo_root() / "data" / "ticks.duckdb")`
- [x] 1.3 Modify `analytics/profiles.yml` — change DuckDB path from `data/ticks.duckdb` to `../data/ticks.duckdb` (relative to `analytics/` directory)
- [x] 1.4 Update `load_ticks.py` `--duckdb-path` default to use `settings.duckdb_path`

## Phase 2: Rebuild Multi-Timeframe Tables

- [x] 2.1 Run `dbt run --full-refresh` from `analytics/` against the canonical DuckDB file — 12 models, all PASS
- [x] 2.2 Run `dbt test` — 37 data tests, all PASS
- [x] 2.3 Verify all 9 `ohlcv_*` tables exist with non-zero rows in the canonical DuckDB (103–450K rows each)

## Phase 3: Cleanup & Verify

- [x] 3.1 Delete `backend/data/ticks.duckdb` (orphan empty file, 274 KB)
- [x] 3.2 Run backend test suite: `uv run pytest` — all 84 tests pass
- [x] 3.3 Quick API smoke test: `GET /api/v1/ohlcv?symbol=MNQ0626&granularity=1m` returns 90,108 bars with real data
