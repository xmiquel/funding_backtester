# Tasks: NinjaTrader Tick Data Pipeline

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~400 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

## Phase 1: Dependencies & Project Scaffold

- [x] 1.1 Add `duckdb>=1.0.0` + `dbt-duckdb` to `backend/pyproject.toml` dependencies
- [x] 1.2 Create `analytics/dbt_project.yml` — dbt profile pointing to `data/ticks.duckdb`
- [x] 1.3 Create `analytics/models/source.yml` — declare DuckDB `raw_ticks` view as dbt source
- [x] 1.4 Verify `/data/` in `.gitignore` (already present) and `data/raw/` exists

## Phase 2: dbt SQL Models

- [x] 2.1 Create `analytics/models/staging/stg_tick_data.sql` — staging view: derive `symbol` from filename stem, `event_ts` from strptime + .NET tick subsecond conversion
- [x] 2.2 Create `analytics/models/marts/dt_tick_data.sql` — full-refresh table: add `spread`, `mid`, `is_aggressive_buy`, `is_aggressive_sell`
- [x] 2.3 Create `analytics/models/marts/tick_load_manifest.sql` — full-refresh audit table: `filename`, `loaded_at`; ordering dependency on `dt_tick_data`

## Phase 3: Loader / Orchestration Script

- [x] 3.1 Create `backend/src/funding_backtester/scripts/__init__.py` and `load_ticks.py` module (importable as `funding_backtester.scripts.load_ticks`)
- [x] 3.2 Implement DuckDB bootstrap: `connect('data/ticks.duckdb')`, `CREATE OR REPLACE VIEW raw_ticks` with filename passthrough and 5-column schema
- [x] 3.3 Implement NT8 file validation: `parse_tick_line()` for 5-column layout, `scan_tick_files()` with graceful empty/missing directory handling
- [x] 3.4 Wire `dbt build` invocation post-bootstrap; scan filenames for manifest context via `run_dbt()` subprocess call

## Phase 4: Unit Tests

- [x] 4.1 Test `event_ts` derivation — strptime + .NET tick math for null, zero, and full-precision subsecond (4 test cases, DuckDB in-memory)
- [x] 4.2 Test aggressor boolean logic — boundary: last==bid, last==ask, same-tick both flags (4 test cases, DuckDB in-memory)
- [x] 4.3 Test NT8 file validation — valid header, malformed columns, empty file, missing directory (7 test cases)

## Phase 5: Integration Tests

- [x] 5.1 Create sample NT8 fixture TXT files in test directory — `backend/tests/data/MNQ0626.txt`, `ES0626.txt`, `__init__.py`
- [x] 5.2 Test full `dbt build` — `test_dbt_integration.py` covers row count, derived columns, symbol extraction, volume preservation (10 pytest tests)
- [x] 5.3 Test manifest recording — `test_manifest_records_filenames` and `test_manifest_has_loaded_at` verify manifest rows match fixture filenames
- [x] 5.4 Test idempotent re-run — `test_idempotent_run_same_row_count` verifies second build produces identical results

## Phase 6: Quality & Cleanup

- [x] 6.1 Run `ruff check` + `mypy` on new Python files; fix issues (zero issues)
- [x] 6.2 dbt integration test harness + schema expectations + CI gate completed:
  - `analytics/models/staging/schema.yml` — not_null expectations for all staging columns
  - `analytics/models/marts/schema.yml` — not_null + unique expectations for final + manifest
  - `.github/workflows/backend-ci.yml` — added `dbt-integration` CI job with `--ignore=test_dbt_integration.py` in main test job
  - `backend/tests/data/` fixtures — committed TXT files for reproducible dbt testing
  - `backend/tests/test_dbt_integration.py` — 11 integration tests, 8.35s runtime
  - `openspec/changes/ninjatrader-tick-pipeline/design.md` — updated Testing Strategy section
