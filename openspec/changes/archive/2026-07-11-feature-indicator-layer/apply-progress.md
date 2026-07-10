# Apply Progress: Feature Indicator Layer

## Mode

Strict TDD

## Delivery

- Strategy: single PR with maintainer-approved `size:exception`
- Review budget: 800 changed lines
- Current observed tracked diff: `git diff --stat` after this batch shows 1,294 insertions and 24 deletions across tracked files, plus untracked indicator package/tests/OpenSpec/dbt model files.
- Review-size status: over budget; do not represent this change as fitting under 800 lines.
- Current work unit: DuckDB/dbt staged indicator persistence proof

## Previous Progress Merged

- Prior Engram observation #105 recorded cleanup of indicator package ruff/mypy blockers across `backend/src/funding_backtester/indicators/` and indicator tests.
- Prior session summary #106 recorded that strict TDD is active and that apply-progress must be merged rather than overwritten.

## Completed Tasks

- [x] 1.1 Add `backend/pyproject.toml` dependency pins for `pandas-ta-classic`, `TA-Lib`, and `vectorbt`, then refresh `backend/uv.lock`.
- [x] 1.2 Update `.github/workflows/backend-ci.yml` to prove Windows and Ubuntu install/runtime import paths, including TA-Lib fallback handling.
- [x] 1.3 Create `backend/src/funding_backtester/indicators/parameters.py` with the bounded SMA/EMA/RSI/MACD/ATR/BBANDS catalog and canonical hash helpers.
- [x] 4.1 Add `backend/tests/test_indicator_dependencies.py` for Windows/Ubuntu import/version proof and TA-Lib availability assertions.
- [x] 4.2 Add `backend/tests/test_indicator_parameters.py` for catalog bounds, deterministic hashes, and rejection of free-form parameters.
- [x] 2.1 Create `backend/src/funding_backtester/indicators/registry.py` to validate catalog-only requests and expose indicator metadata/output names.
- [x] Corrective blocker: make the indicator mart integration test deterministic when run alone and in the full dbt integration file.
- [x] Corrective blocker: update review-size metadata and task wording so the `size:exception` and partial engine/test state are explicit.
- [x] Corrective blocker: cover the public package-root registry export contract for task 2.1.
- [x] 2.2 Complete `backend/src/funding_backtester/indicators/engine.py` real-engine proof with pandas/pandas-ta-classic OHLCV DataFrame computation and backend metadata.
- [x] 4.3 Complete `backend/tests/test_indicator_engine.py` real tests for golden pandas fixtures, backend metadata, and insufficient-lookback behavior.
- [x] Corrective blocker: align MACD catalog `min_lookback` with the first row where all MACD outputs are complete.
- [x] Corrective blocker: harden the pandas indicator engine against empty frames, missing OHLCV columns, and short lookback windows with deterministic domain behavior.
- [x] Corrective blocker: align TA-Lib fallback handling across `quality`, `test`, and `dbt-integration` CI jobs.
- [x] Corrective blocker: align the non-pandas/protocol MACD fallback with the catalog output contract, including `macd_hist`.
- [x] 2.3 Create `backend/src/funding_backtester/indicators/duckdb_io.py` plus `analytics/models/marts/indicator_features.sql` for staged persistence and idempotent dbt materialization.
- [x] Corrective blocker: harden task 2.3 persistence so reruns are deterministic, empty source reruns clear staged rows, source model identifiers are validated before SQL interpolation, replacement runs in a DuckDB transaction, and dbt tests cover non-null/unique mart contracts.
- [x] Corrective blocker: strengthen task 2.3 integration coverage so the external `indicator_features` mart rows, including `computed_at`, are snapshotted after the first build and asserted unchanged after rerun.
- [x] 2.4 Add `backend/scripts/build_indicator_features.py` to run local/CI feature builds from DuckDB sources.
- [x] 3.1 Create `backend/src/funding_backtester/indicators/vectorbt_loader.py` to return aligned close/features Series/DataFrames for vectorbt.
- [x] 3.2 Update `analytics/models/marts/schema.yml` and any dbt references so feature keys, hashes, and reproducibility columns are constrained.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 / 4.1 | `backend/tests/test_indicator_dependencies.py` | Unit dependency proof | N/A (dependency proof file was the test driver for this batch) | ✅ `uv run pytest tests/test_indicator_dependencies.py -q` failed with missing `pandas-ta-classic`, `TA-Lib`, and `vectorbt` before dependency pins were added | ✅ `uv run pytest tests/test_indicator_dependencies.py -q` passed: 2 passed | ✅ Two behaviors covered: import resolution and version metadata for all required indicator packages | ✅ `uv run ruff check tests/test_indicator_dependencies.py --fix`, then ruff passed |
| 1.2 | `.github/workflows/backend-ci.yml` + `backend/tests/test_indicator_dependencies.py` | CI dependency proof | ✅ `uv run pytest tests/test_indicator_dependencies.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` passed: 12 passed before workflow edit | ✅ Workflow was updated after the existing dependency proof test existed; the test proves runtime imports while CI now runs it on Ubuntu and Windows | ✅ Focused dependency/catalog/engine tests passed after workflow fallback update: 12 passed | ✅ Matrix covers Ubuntu and Windows; Ubuntu has a resolver-first TA-Lib C-library fallback path | ✅ YAML kept scoped to existing backend CI workflow; no remote-only workflow was hallucinated |
| 1.3 / 4.2 | `backend/tests/test_indicator_parameters.py` | Unit catalog contract | ✅ Existing catalog/engine tests passed before catalog edits: 6 passed | ✅ Tests first failed with `ModuleNotFoundError: No module named 'funding_backtester.indicators.parameters'` | ✅ `uv run pytest tests/test_indicator_parameters.py -q` passed: 6 passed | ✅ Catalog coverage includes SMA/EMA/RSI/MACD/ATR/BBANDS outputs/lookbacks plus free-form override rejection and stable identity | ✅ Extracted `parameters.py`; left `catalog.py` as compatibility exports; ruff and mypy passed |
| Corrective deterministic dbt integration | `backend/tests/test_dbt_integration.py` | Integration | ✅ RED reproduced first: isolated original test failed with baseline rows `ES0626=1/3`, `MNQ0626=1/11` while it expected post-mutation rows | ✅ Original order-dependent expectation failed when run alone before code changes | ✅ Isolated renamed test passed: `1 passed`; full `tests/test_dbt_integration.py` passed: `20 passed` | ✅ Proves both isolated and full-file execution; fresh `isolated_dbt_env` prevents dependence on session-scoped mutations | ✅ Extracted `_build_dbt_database` helper and kept tests green after refactor |
| Corrective artifact truthfulness | `openspec/changes/feature-indicator-layer/tasks.md`, `design.md`, `apply-progress.md` | SDD artifact | N/A (documentation/artifact correction) | ✅ Review findings showed stale 500-700 line estimate, misleading vectorbt-readiness name, and ambiguous unchecked engine/test tasks | ✅ Artifacts now state observed `git diff --stat` scale, `size:exception`, and partial/scaffolding status for 2.2/4.3 | ➖ Single corrective metadata scenario | ✅ Removed stale CI wording from `design.md`; no task was falsely marked complete |
| 2.1 | `backend/tests/test_indicator_registry.py` | Unit registry contract | ✅ `uv run pytest tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` passed: 10 passed before adding registry exports | ✅ `uv run pytest tests/test_indicator_registry.py -q` failed with `ModuleNotFoundError: No module named 'funding_backtester.indicators.registry'` | ✅ `uv run pytest tests/test_indicator_registry.py -q` passed: 3 passed after creating `registry.py` | ✅ Covered valid MACD metadata, free-form RSI rejection, and stable bounded sorted metadata list including BBANDS outputs | ✅ Exported registry helpers from package `__init__`; focused tests, ruff, and mypy stayed green |
| 2.1 corrective package-root contract | `backend/tests/test_indicator_registry.py` | Unit public export contract | ✅ `uv run pytest tests/test_indicator_registry.py -q` passed: 3 passed before adding corrective coverage | ⚠️ Corrective test was written first for the previously untested public package-root contract, but it passed immediately because production exports already existed; no production change was made | ✅ `uv run pytest tests/test_indicator_registry.py -q` passed: 4 passed | ✅ Root-level behavior covers `IndicatorRequest`, `validate_indicator_request`, `describe_indicator`, `list_indicator_metadata`, and deterministic free-form rejection through `funding_backtester.indicators` | ✅ Test-only change; ruff passed |
| 2.2 / 4.3 | `backend/tests/test_indicator_engine.py` | Unit real-engine proof | ✅ `uv run pytest tests/test_indicator_engine.py -q` passed: 4 passed before engine edits | ✅ Added pandas DataFrame tests first; `uv run pytest tests/test_indicator_engine.py -q` failed: 3 failed because SMA/BBANDS were unsupported and metadata did not exist | ✅ Implemented pandas-backed `sma`, `ema`, `rsi`, `macd`, `atr`, and `bbands`; `uv run pytest tests/test_indicator_engine.py -q` passed: 7 passed | ✅ Covered all six cataloged indicators, backend metadata, and insufficient-lookback NaN rows with non-empty output after lookback | ✅ Replaced typed direct imports for untyped pandas/pandas-ta-classic with runtime imports so `uv run mypy src/funding_backtester/indicators` stays green |
| Corrective 2.2 / 4.3 reliability and resilience | `backend/tests/test_indicator_engine.py`, `backend/tests/test_indicator_parameters.py`, `backend/tests/test_indicator_registry.py` | Unit engine/catalog contract | ✅ `uv run pytest tests/test_indicator_engine.py -q` passed: 7 passed before corrective edits | ✅ First RED failed on missing `IndicatorComputationError`; combined tests then failed on stale MACD `min_lookback=26` expectations | ✅ `uv run pytest tests/test_indicator_engine.py -q` passed: 9 passed; combined indicator tests passed: 19 passed | ✅ Added deterministic EMA, MACD, BBANDS lower/middle/upper, MACD lookback, short-frame NA, empty-frame, and missing-column cases | ✅ Domain error and short-frame helpers kept focused; full ruff and mypy passed |
| Corrective CI fallback alignment | `.github/workflows/backend-ci.yml` | CI dependency resilience | ✅ Existing workflow had fallback only in `quality` | ✅ Workflow review identified `test` and `dbt-integration` ran bare `uv sync --frozen --extra dev` without the fallback path | ✅ YAML parsed with `python -c "import pathlib, yaml; yaml.safe_load(...)"`; no local GitHub runner available | ✅ Resolver-first fallback block is now consistent in all Ubuntu jobs that install backend dependencies | ✅ Kept workflow-only scope and did not add new tooling |
| Corrective 2.2 / 4.3 protocol MACD output contract | `backend/tests/test_indicator_engine.py` | Unit protocol fallback contract | ✅ `uv run pytest tests/test_indicator_engine.py -q` passed: 9 passed before corrective edits | ✅ New protocol-path MACD behavior test failed because result columns were `("macd", "macd_signal")` instead of catalog outputs `("macd", "macd_signal", "macd_hist")` | ✅ `uv run pytest tests/test_indicator_engine.py -q` passed: 10 passed after minimal fallback fix | ✅ Test asserts catalog output parity, result frame keys, and concrete MACD/signal/histogram values from the protocol path | ✅ Production change kept to computing `macd_hist = macd - macd_signal`; full ruff and mypy passed |
| 2.3 | `backend/tests/test_dbt_integration.py` | dbt/DuckDB integration | ⚠️ Safety net was not run before editing the existing integration test file; focused class and full file passed after implementation | ✅ New test first failed during collection with `ModuleNotFoundError: No module named 'funding_backtester.indicators.duckdb_io'` | ✅ `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_stage_materializes_idempotent_long_form_rows -q` passed: 1 passed | ✅ Covered stage creation, rerun replacement idempotency, dbt mart materialization, uniqueness, metadata, and empty short-lookback values for both symbols | ✅ Exported the public stage builder and kept ruff, mypy, focused integration tests, and full dbt integration green |
| Corrective 2.3 persistence blockers | `backend/tests/test_dbt_integration.py`, `analytics/models/marts/schema.yml`, `analytics/tests/assert_indicator_features_unique.sql` | dbt/DuckDB integration | ✅ `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration -q` passed: 3 passed before corrective edits | ✅ New deterministic/empty-source and invalid-source tests failed: `computed_at` differed per symbol and invalid `source_model` reached DuckDB SQL parsing | ✅ Corrective tests passed: 2 passed; focused integration class passed: 5 passed | ✅ Covered deterministic `computed_at`, same-source empty rerun clearing stale rows, source identifier rejection, dbt `build` of `indicator_features`, non-null schema tests, and a singular logical uniqueness test | ✅ Removed `select distinct` from the mart so duplicate logical rows are not hidden; replacement now validates requests up front and performs delete/insert inside a DuckDB transaction |
| Corrective 2.3 external mart determinism proof | `backend/tests/test_dbt_integration.py` | dbt/DuckDB integration | ✅ `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration -q` passed: 5 passed before test-only corrective edit | ✅ Test strengthened first to snapshot `indicator_features` after the first dbt build and compare against the rerun mart rows including `computed_at` | ✅ Focused deterministic test passed: 1 passed; focused class passed: 5 passed; full dbt integration passed: 23 passed | ✅ The contract now checks same input produces byte-for-byte equal external mart rows across reruns, rather than only checking final stage row timestamps | ✅ Test-only change; no production bug was exposed |
| 2.4 | `backend/tests/test_build_indicator_features.py` | CLI / Integration | ✅ `uv run pytest tests/test_indicator_parameters.py tests/test_indicator_engine.py tests/test_indicator_registry.py -q` passed: 20 passed before adding CLI build script | ✅ Test written first: `ModuleNotFoundError: No module named 'funding_backtester.scripts.build_indicator_features'` | ✅ `uv run pytest tests/test_build_indicator_features.py -q` passed: 10 passed after creating `build_indicator_features.py` | ✅ CLI follows `load_ticks.py` pattern: `build()` function + `main()` entry point with argparse for DuckDB path, source model, timeframe, feature names, dbt project dir, and skip-dbt flag | ✅ Ruff and mypy pass |
| 3.1 | `backend/tests/test_indicator_vectorbt_loader.py` | Unit (DuckDB-backed) | N/A (new file) | ✅ Test written first: `ModuleNotFoundError: No module named 'funding_backtester.indicators.vectorbt_loader'` | ✅ `uv run pytest tests/test_indicator_vectorbt_loader.py -q` passed: 9 passed after creating `vectorbt_loader.py` | ✅ 9 tests cover basic structure, symbol isolation, column naming with parameter hash, empty/no-data, feature filter, sorted index, multi-output MACD columns, close/feature alignment, and missing stage table error | ✅ Ruff + mypy pass after fixing UP032 f-string, line-length issues, and adding pandas import ignore |
| 3.2 | `analytics/models/marts/schema.yml`, `analytics/tests/assert_indicator_features_unique.sql` | dbt schema/tests | ✅ `uv run pytest tests/test_dbt_integration.py -q` passed: 23 passed before schema edits | ⚠️ SDD task applied to dbt configuration, not unit code — RED was dbt build failing on YAML syntax error and missing `dbt_utils` package | ✅ `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration -q` passed: 5 passed; full dbt integration: 23 passed | ✅ Added `value` and `talib_version` columns to schema.yml with descriptions; `feature_name` has `accepted_values` constraint for all 6 catalog entries; `loaded_at` column indentation was also fixed; strong uniqueness singular test including `computed_at` | ✅ `uv run ruff check src/` + `uv run mypy src/` pass; YAML is valid |
| 3.3 | `backend/src/funding_backtester/api/v1/features.py`, `backend/tests/test_features_api.py` | API read-only endpoints | ✅ Safety net: 41 focused indicator tests + 23 dbt integration tests + ruff + mypy all passing before implementation | ✅ 16 tests in `test_features_api.py` failed: 6 catalog tests got 200, 10 DB-dependent tests got 404 because router was not yet wired; then all 16 failed after wiring because `asyncio.run` inside async endpoints raised `RuntimeError` | ✅ All 16 tests passed after refactoring to use direct `duckdb.connect` instead of async `DuckDBClient` wrapper | ✅ 3 endpoints: catalog (static), meta (DISTINCT symbols/timeframes/source_models), features (full query with symbol/timeframe/feature_name filters) | ✅ Ruff + mypy pass; all existing tests pass (57 focused + 23 dbt integration + 43 OHLCV/health) |

## Test Summary

- **Total tests written/updated**: 52 (35 prior + 16 new for task 3.3 + 1 new/e2e fix for task 4.4)
- **Total tests passing**: 24 dbt integration tests + 9 vectorbt loader tests + 22 focused indicator tests + 16 feature API tests
- **Layers verified**: dbt schema/tests now include `not_null` on all metadata columns, `accepted_values` for `feature_name` catalog, and a strengthened singular uniqueness test including `computed_at` as a deterministic reproducibility assertion
- **Layers used**: Unit dependency proof, unit catalog contract, unit registry contract, unit real-engine proof, unit DuckDB-backed loader, dbt integration
- **Approval tests**: None — no refactoring task in this batch
- **Pure functions created**: 0

| 4.4 (RED exposed bug) | `backend/tests/test_dbt_integration.py` | dbt/DuckDB integration end-to-end + production fix | ✅ Safety net: 32 vectorbt + dbt tests passed before edit | ✅ RED: e2e test(`test_indicator_e2e_full_path_persistence_loader_idempotent`) failed because `_load_feature_frame` returned empty DataFrame when all feature values are NaN (short OHLCV data below lookback) | ✅ Fixed `vectorbt_loader.py` — `_load_feature_frame` now builds expected columns + datetime index from source rows when `pivot_table` returns empty due to all-NaN values | ✅ Two paths covered: NaN-all features (below lookback) and normal non-NaN features (pre-existing triage through `pivot_table`) | ✅ `ruff` and `mypy` passed on modified file |

## Commands and Results

- `uv run pytest tests/test_indicator_dependencies.py -q` → RED: 2 failed before dependency pins were added.
- `uv lock` → refreshed `backend/uv.lock`; added `pandas-ta-classic`, `TA-Lib`, `vectorbt`, and transitive packages.
- `uv run pytest tests/test_indicator_dependencies.py -q` → GREEN: 2 passed.
- `uv run ruff check tests/test_indicator_dependencies.py --fix` → fixed import ordering.
- `uv run ruff check tests/test_indicator_dependencies.py` → passed.
- `uv run pytest tests/test_indicator_dependencies.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → 8 passed.
- `uv run mypy src/funding_backtester/indicators` → passed.
- `uv run pytest tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → Safety net before corrective catalog edits: 6 passed.
- `uv run pytest tests/test_indicator_parameters.py -q` → RED: failed because `funding_backtester.indicators.parameters` did not exist.
- `uv run pytest tests/test_indicator_parameters.py -q` → GREEN: 6 passed after `parameters.py` and catalog validation were added.
- `uv run pytest tests/test_indicator_engine.py -q` → GREEN after engine tests were aligned to catalog-only parameters: 4 passed.
- `uv run pytest tests/test_indicator_dependencies.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → 12 passed.
- `uv run ruff check src/funding_backtester/indicators tests/test_indicator_parameters.py tests/test_indicator_engine.py tests/test_indicator_dependencies.py --fix` → fixed import order.
- `uv run ruff check src/funding_backtester/indicators tests/test_indicator_parameters.py tests/test_indicator_engine.py tests/test_indicator_dependencies.py` → passed.
- `uv run mypy src/funding_backtester/indicators` → passed.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_vector_is_vectorbt_ready -q` → RED reproduced: failed when run alone with baseline rows instead of post-mutation totals.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_uses_baseline_ohlcv_summary -q` → GREEN: 1 passed.
- `uv run pytest tests/test_dbt_integration.py -q` → GREEN: 20 passed.
- `uv run pytest tests/test_indicator_dependencies.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → GREEN: 12 passed.
- `uv run ruff check tests/test_dbt_integration.py` → passed.
- `uv run mypy src/funding_backtester/indicators` → passed.
- `git diff --stat` → observed tracked diff: 1,179 insertions and 22 deletions, plus untracked indicator package/tests/OpenSpec files.
- `uv run pytest tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → Safety net before registry task: 10 passed.
- `uv run pytest tests/test_indicator_registry.py -q` → RED: failed with missing `funding_backtester.indicators.registry` before production code existed.
- `uv run pytest tests/test_indicator_registry.py -q` → GREEN: 3 passed after registry implementation.
- `uv run pytest tests/test_indicator_registry.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → GREEN: 13 passed.
- `uv run ruff check src/funding_backtester/indicators tests/test_indicator_registry.py` → passed.
- `uv run mypy src/funding_backtester/indicators` → passed.
- `uv run pytest tests/test_indicator_registry.py -q` → Safety net before corrective package-root coverage: 3 passed.
- `uv run pytest tests/test_indicator_registry.py -q` → Corrective public package-root coverage passed immediately: 4 passed; no production bug was exposed.
- `uv run ruff check tests/test_indicator_registry.py` → passed.
- `uv run pytest tests/test_indicator_registry.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → GREEN: 14 passed.
- `uv run pytest tests/test_indicator_engine.py -q` → Safety net before engine task: 4 passed.
- `uv run pytest tests/test_indicator_engine.py -q` → RED: 3 failed because `sma` and `bbands` were unsupported and `IndicatorResult.metadata` did not exist.
- `uv run pytest tests/test_indicator_engine.py -q` → GREEN: 7 passed after pandas-backed engine implementation.
- `uv run pytest tests/test_indicator_registry.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → GREEN: 17 passed.
- `uv run ruff check src/funding_backtester/indicators tests/test_indicator_engine.py` → passed.
- `uv run mypy src/funding_backtester/indicators` → passed.
- `uv run pytest tests/test_indicator_engine.py -q` → Safety net before corrective reliability/resilience edits: 7 passed.
- `uv run pytest tests/test_indicator_engine.py -q` → RED: failed during collection because `IndicatorComputationError` did not exist yet.
- `uv run pytest tests/test_indicator_engine.py -q` → GREEN: 9 passed after MACD lookback, domain errors, and deterministic short-frame behavior were implemented.
- `uv run pytest tests/test_indicator_registry.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → RED during triangulation: 3 stale MACD `min_lookback=26` assertions failed after catalog correction.
- `uv run pytest tests/test_indicator_registry.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → GREEN: 19 passed.
- `uv run ruff check src/funding_backtester/indicators tests/test_indicator_engine.py tests/test_indicator_registry.py tests/test_indicator_parameters.py` → passed.
- `uv run mypy src/funding_backtester/indicators` → passed.
- `python -c "import pathlib, yaml; yaml.safe_load(pathlib.Path('.github/workflows/backend-ci.yml').read_text())"` → passed; YAML parsed successfully.
- `uv run ruff check .` → passed.
- `uv run mypy src/` → passed: 23 source files checked.
- `uv run pytest tests/test_indicator_engine.py -q` → Safety net before protocol MACD corrective edit: 9 passed.
- `uv run pytest tests/test_indicator_engine.py -q` → RED: new protocol-path MACD contract test failed because fallback returned only `("macd", "macd_signal")`.
- `uv run pytest tests/test_indicator_engine.py -q` → GREEN: 10 passed after adding `macd_hist` to the non-pandas/protocol fallback.
- `uv run pytest tests/test_indicator_registry.py tests/test_indicator_parameters.py tests/test_indicator_engine.py -q` → GREEN: 20 passed.
- `uv run ruff check .` → passed.
- `uv run mypy src/` → passed: 23 source files checked.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_stage_materializes_idempotent_long_form_rows -q` → RED: failed during collection because `funding_backtester.indicators.duckdb_io` did not exist.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_stage_materializes_idempotent_long_form_rows -q` → GREEN: 1 passed after adding `duckdb_io.py` and `indicator_features.sql`.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration -q` → GREEN: 3 passed.
- `uv run ruff check src/funding_backtester/indicators tests/test_dbt_integration.py` → passed.
- `uv run mypy src/funding_backtester/indicators` → passed: 6 source files checked.
- `uv run pytest tests/test_dbt_integration.py -q` → passed: 21 passed.
- `git diff --stat` → observed tracked diff: 1,294 insertions and 24 deletions across tracked files, plus untracked indicator package/tests/OpenSpec/dbt model files.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration -q` → Safety net before corrective task 2.3 edits: 3 passed.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_rerun_is_deterministic_and_clears_empty_source tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_rejects_invalid_source_model -q` → RED: 2 failed because `computed_at` drifted and invalid `source_model` reached DuckDB SQL parsing.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_rerun_is_deterministic_and_clears_empty_source tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_rejects_invalid_source_model -q` → GREEN: 2 passed after deterministic timestamping, source-model validation, and atomic replacement changes.
- `uv run pytest tests/test_dbt_integration.py -q` → passed: 23 passed.
- `uv run ruff check src/funding_backtester/indicators tests/test_dbt_integration.py --fix` → fixed import ordering.
- `uv run ruff check .` → passed.
- `uv run mypy src/` → passed: 24 source files checked.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration -q` → passed: 5 passed after ruff formatting.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration -q` → Safety net before external mart determinism test correction: 5 passed.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_feature_rerun_is_deterministic_and_clears_empty_source -q` → GREEN: 1 passed after strengthening the test to compare first-build and rerun `indicator_features` mart rows including `computed_at`; no production change required.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration -q` → passed: 5 passed.
- `uv run ruff check tests/test_dbt_integration.py` → passed.
- `uv run pytest tests/test_dbt_integration.py -q` → passed: 23 passed.
- `uv run mypy src/` → passed: 24 source files checked.
- `uv run pytest tests/test_build_indicator_features.py -q` → RED: 1 error during collection: `ModuleNotFoundError` for `build_indicator_features`.
- `uv run pytest tests/test_build_indicator_features.py -q` → GREEN: 10 passed after creating `build_indicator_features.py`.
- `uv run ruff check src/funding_backtester/scripts/build_indicator_features.py tests/test_build_indicator_features.py --fix` → 3 fixable errors fixed.
- `uv run mypy src/` → passed: 25 source files checked.
- `uv run pytest tests/test_build_indicator_features.py tests/test_indicator_parameters.py tests/test_indicator_engine.py tests/test_indicator_dependencies.py tests/test_indicator_registry.py -q` → 32 passed.
- `uv run pytest tests/test_dbt_integration.py -q` → 23 passed.
- `uv run pytest tests/test_indicator_dependencies.py tests/test_indicator_parameters.py tests/test_indicator_engine.py tests/test_indicator_registry.py tests/test_build_indicator_features.py -q` → Safety net before task 3.1: 32 passed.
- `uv run pytest tests/test_indicator_vectorbt_loader.py -q` → RED: `ModuleNotFoundError: No module named 'funding_backtester.indicators.vectorbt_loader'`.
- `uv run pytest tests/test_indicator_vectorbt_loader.py -q` → GREEN: 7 passed after creating `vectorbt_loader.py`.
- `uv run pytest tests/test_indicator_vectorbt_loader.py -q` → GREEN after triangulation: 9 passed (multi-output MACD + alignment tests).
- `uv run ruff check src/funding_backtester/indicators/vectorbt_loader.py tests/test_indicator_vectorbt_loader.py --fix` → UP032 f-string fix applied; line-length issues in test fixed manually.
- `uv run ruff format src/funding_backtester/indicators/vectorbt_loader.py` → reformatted.
- `uv run ruff check src/funding_backtester/indicators/vectorbt_loader.py tests/test_indicator_vectorbt_loader.py` → passed.
- `uv run mypy src/` → passed: 26 source files checked.
- `uv run pytest tests/test_indicator_dependencies.py tests/test_indicator_parameters.py tests/test_indicator_engine.py tests/test_indicator_registry.py tests/test_build_indicator_features.py tests/test_indicator_vectorbt_loader.py -q` → 41 passed.
- `uv run pytest tests/test_features_api.py -q` → RED: 16 failed (404 before router existed → 10 failed on `asyncio.run` → GREEN: 16 passed after fixing to direct DuckDB connections).
- `uv run pytest tests/test_dbt_integration.py -q` → GREEN: 23 passed (existing tests still pass).
- `uv run pytest tests/test_ohlcv.py tests/test_health.py -q` → GREEN: 43 passed (existing API tests still pass).
- `uv run pytest tests/test_features_api.py tests/test_indicator_dependencies.py tests/test_indicator_parameters.py tests/test_indicator_engine.py tests/test_indicator_registry.py tests/test_build_indicator_features.py tests/test_indicator_vectorbt_loader.py -q` → 57 passed (41 prior + 16 new).
- `uv run ruff check src/` → passed.
- `uv run mypy src/` → passed: 27 source files checked.

## Remaining Tasks

- [x] 3.3 Wire backend/dbt consumers so persisted features are discoverable without exposing indicator internals.
- [x] 4.4 Extend `backend/tests/test_dbt_integration.py` to verify stage build, dbt persistence, idempotency, and vectorbt-aligned output.
- [x] 5.1 Document the feature mart contract, dependency proof steps, and fallback installation notes where backend/dbt docs live.
- [x] 5.2 Remove any temporary scaffolding after tests pass and confirm the final artifact set matches the design.

## Task 5.1 — Documentation Creation

Created `backend/docs/indicator-features.md` covering:
- Full `indicator_features` mart contract: all 16 columns with types and descriptions, logical uniqueness key `(datetime, symbol, timeframe, source_model, feature_id, output_name)`, `feature_id` derivation from source_model + symbol + timeframe + canonical_parameter_json + computation_version.
- Bounded catalog table: SMA/EMA/RSI/MACD/ATR/BBANDS with library, parameters, outputs, and min_lookback.
- SQL query examples: all features for a symbol, specific feature filtering, metadata inspection.
- Dependency proof: required packages (`pandas-ta-classic`, `TA-Lib`, `vectorbt`), proof test command, manual verification snippet.
- TA-Lib fallback installation: full Ubuntu CI fallback steps (apt-get, source build, retry), Windows local wheel recovery path, macOS note.
- CLI entry point usage examples.
- Python API quick reference: `build_indicator_feature_stage`, `compute_indicator_series`, `load_features`.

No existing doc pattern found in the repo — created `backend/docs/` as the docs location.

## Notes

- `pandas-ta-classic` installs as import module `pandas_ta_classic` in this resolved environment.
- Existing uncommitted indicator package and dbt integration changes from the prior batch were preserved.
- Artifact delivery strategy is now consistent: this change is a single PR with maintainer-approved `size:exception`; no chained PR strategy applies.
- Local `.github/workflows/backend-ci.yml` exists and was updated directly. It now runs focused dependency import proof in CI and includes an Ubuntu TA-Lib fallback after standard `uv sync` fails.
- Full vectorbt loader proof is complete under 3.1; persistence proof remains under 4.4; engine-level pandas/pandas-ta-classic proof is complete under 2.2/4.3.
- The dbt indicator mart test no longer claims vectorbt readiness; it now proves deterministic baseline OHLCV summary input for the indicator boundary. Real vectorbt proof is complete under 3.1; end-to-end persistence+loading proof remains under 4.4.
- Registry task 2.1 is complete and remains intentionally metadata-only; real pandas-backed computation is now covered under 2.2/4.3.
- Task 2.1 now has behavior-focused coverage for the externally visible `funding_backtester.indicators` package-root registry contract. The corrective test passed immediately because the exports were already present, so production code was left unchanged.
- The engine now accepts real pandas DataFrames and uses the `pandas-ta-classic` DataFrame accessor for SMA, EMA, RSI, MACD, ATR, and BBANDS. Fake-frame compatibility remains for the previous narrow tests. Persistence is complete under 2.3; vectorbt loading is complete under 3.1; end-to-end proof remains under 4.4.
- Backend metadata is now present on `IndicatorResult` and records `pandas_ta_classic_version`, TA-Lib availability/version, and whether the cataloged execution path requested TA-Lib-backed use.
- MACD catalog `min_lookback` is now 34 because default MACD output is not complete until index 33 (`macd`, `macd_signal`, and `macd_hist` all non-NA). This prevents downstream consumers from trusting row 25-32 as complete MACD feature rows.
- Pandas DataFrame computation now fails fast with `IndicatorComputationError` for empty OHLCV frames and missing required OHLCV columns, including the indicator name and deterministic context in the error message. Frames shorter than the catalog lookback degrade to full-length output frames with catalog output columns filled with `NA`.
- The CI TA-Lib fallback remains resolver-first and is now aligned across `quality`, `test`, and `dbt-integration`; local validation was limited to YAML parsing because GitHub Actions execution is remote-only.
- The non-pandas/protocol MACD fallback now matches the catalog and pandas path by returning `macd`, `macd_signal`, and `macd_hist`; the fallback is preserved for existing protocol tests instead of being removed.
- `duckdb_io.build_indicator_feature_stage` now reads persisted OHLCV models from DuckDB, computes cataloged features per symbol, replaces prior rows for the same feature identity, and writes long-form `indicator_feature_stage` rows with reproducibility metadata. The dbt `indicator_features` mart publishes staged rows and safely builds empty when the stage table is absent.
- Task 4.4 is now complete. The e2e test `test_indicator_e2e_full_path_persistence_loader_idempotent` exercises the full path: stage build → dbt mart → vectorbt loader → idempotent rerun. A real bug was exposed and fixed during RED: `_load_feature_frame` in `vectorbt_loader.py` returned an empty DataFrame when all feature values are NaN (OHLCV data shorter than indicator lookback for both ES0626 and MNQ0626). The fix preserves output columns and datetime index even when `pivot_table` returns empty.
- Corrective task 2.3 now derives stable `computed_at` from the source input max `datetime` instead of wall-clock time. The column remains in the mart because the spec/design require reproducibility metadata, but reruns with identical input now produce deterministic outputs.
- Corrective task 2.3 now deletes and reinserts rows for the requested source/timeframe/features inside one DuckDB transaction. Empty same-source reruns clear stale stage rows, and `indicator_features` no longer uses `select distinct`, so dbt tests can expose duplicate logical rows instead of hiding them.
- `source_model` is now limited to simple SQL identifiers before interpolation and invalid identifiers fail with a deterministic domain `ValueError`.
- `analytics/models/marts/schema.yml` now documents/tests `indicator_features` not-null columns, and `analytics/tests/assert_indicator_features_unique.sql` checks the logical uniqueness key `(datetime, symbol, timeframe, source_model, feature_id, output_name)`.
- The deterministic task 2.3 test now proves the external mart contract directly: after first build and rerun, complete `indicator_features` rows for the source are equal including `computed_at`, so a volatile-but-row-consistent per-run timestamp would fail the test.
- Task 2.4 is complete. `build_indicator_features.py` follows the same `build()` + `main()` pattern as `load_ticks.py`. It delegates to `build_indicator_feature_stage` from `duckdb_io.py` for the actual computation and writes stage rows. The dbt build is invoked via `subprocess.run` with `DBT_DUCKDB_PATH` env var, matching the dbt integration test pattern. When `--skip-dbt` is set, only stage writing runs.
- Tests for task 2.4 use `mock.patch("subprocess.run")` to avoid running dbt (which requires a fully bootstrapped DuckDB with DuckDB extension loading that is environment-dependent). The pre-existing `_build_dbt_database` helper bootstraps the full dbt DAG for the fixture data before tests exercise the CLI script.
- Task 3.3 is complete. Three GET endpoints expose features without exposing indicator internals:
  - `GET /api/v1/features/catalog` — static indicator catalog (no DB dependency)
  - `GET /api/v1/features/meta` — available symbols/timeframes/source_models from persisted features
  - `GET /api/v1/features` — query persisted feature rows with symbol (required), timeframe (optional), feature_name (optional, multiple allowed)
- The feature endpoints use direct `duckdb.connect` (read-only) instead of the async `DuckDBClient` singleton because the feature queries are per-request transactions against the same DuckDB database, and the endpoints gracefully handle missing database files or missing feature tables.
- `LOGIN` note: The meta endpoint queries `indicator_feature_stage` or `indicator_features` via `SELECT DISTINCT symbol, timeframe, source_model` — whichever table exists first. The features endpoint uses the same resolution order.
- The Pydantic schemas `FeatureCatalogEntry`, `FeatureMetaResponse`, and `FeatureRow` in `schemas/api.py` define the API contract. `FeatureRow.datetime` has a `# type: ignore[valid-type]` on `computed_at` because the field name shadows the `datetime` import — a known mypy limitation with Pydantic models.

## Task 5.2 — Scaffolding Cleanup and Artifact Verification

### Scanned for Scaffolding

- Searched for `# TODO`, `# FIXME`, `# HACK`, `# XXX`, `# TEMP`, `# scaffold`, `# placeholder` across all indicator source and test files — **none found**.
- Searched for `pass` as standalone statement in indicator source files — **none found**.
- Inspected all indicator source files (`__init__.py`, `parameters.py`, `registry.py`, `engine.py`, `duckdb_io.py`, `vectorbt_loader.py`, `catalog.py`) — no commented-out code, no placeholder implementations, no scaffolding.
- Checked for test files marked as temporary/placeholder — **none found**.
- Internal `placeholders` variables in `vectorbt_loader.py` and `duckdb_io.py` are normal SQL parameterized query patterns, not scaffolding.

### Final Artifact Set vs. Design

| Design File | Status |
|------------|--------|
| `backend/pyproject.toml`, `backend/uv.lock` | ✅ Modified |
| `.github/workflows/backend-ci.yml` | ✅ Modified |
| `backend/src/funding_backtester/indicators/parameters.py` | ✅ Created |
| `backend/src/funding_backtester/indicators/registry.py` | ✅ Created |
| `backend/src/funding_backtester/indicators/engine.py` | ✅ Completed (was partial scaffolding → real pandas-backed engine) |
| `backend/src/funding_backtester/indicators/duckdb_io.py` | ✅ Created |
| `backend/src/funding_backtester/indicators/vectorbt_loader.py` | ✅ Created |
| `backend/scripts/build_indicator_features.py` | ✅ Created |
| `analytics/models/marts/indicator_features.sql` | ✅ Created |
| `analytics/models/marts/schema.yml` | ✅ Updated |
| `backend/tests/test_indicator_dependencies.py` | ✅ Created |
| `backend/tests/test_indicator_parameters.py` | ✅ Created |
| `backend/tests/test_indicator_engine.py` | ✅ Completed (was partial → full real-engine tests) |
| `backend/tests/test_dbt_integration.py` | ✅ Extended |

**Additional files created** (matching design intent):
- `backend/src/funding_backtester/indicators/__init__.py` — package exports
- `backend/src/funding_backtester/indicators/catalog.py` — compatibility exports
- `backend/tests/test_indicator_registry.py` — registry tests
- `backend/tests/test_indicator_build_indicator_features.py` → `test_build_indicator_features.py` — CLI tests
- `backend/tests/test_indicator_vectorbt_loader.py` — loader tests
- `backend/src/funding_backtester/api/v1/features.py` — API endpoints (task 3.3)
- `backend/tests/test_features_api.py` — API tests
- `backend/docs/indicator-features.md` — documentation (task 5.1)
- `analytics/tests/assert_indicator_features_unique.sql` — dbt test
- `openspec/changes/feature-indicator-layer/apply-progress.md` — apply progress

### Quality Gates

- ✅ Ruff: all checks passed
- ✅ Mypy: 27 source files, no issues
- ✅ Tests: 57 indicator tests + 24 dbt integration tests + 43 OHLCV/health tests = **124 passed**
- ✅ Fixed one E501 line-length issue in `test_dbt_integration.py` docstring

### Commands and Results

- `uv run ruff check src/funding_backtester/indicators/ src/funding_backtester/api/v1/features.py src/funding_backtester/scripts/build_indicator_features.py tests/test_indicator_*.py tests/test_features_api.py tests/test_dbt_integration.py` → All checks passed (after fixing one E501)
- `uv run mypy src/` → Success: no issues found in 27 source files
- `uv run pytest tests/test_indicator_dependencies.py tests/test_indicator_parameters.py tests/test_indicator_engine.py tests/test_indicator_registry.py tests/test_build_indicator_features.py tests/test_indicator_vectorbt_loader.py tests/test_features_api.py -q` → 57 passed
- `uv run pytest tests/test_dbt_integration.py -q` → 24 passed
- `uv run pytest tests/test_ohlcv.py tests/test_health.py -q` → 43 passed

## Task 4.4 Commands

- `uv run pytest tests/test_indicator_vectorbt_loader.py -q` → SAFETY NET: 9 passed before edit.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_e2e_full_path_persistence_loader_idempotent -q` → RED: 1 failed because `_load_feature_frame` returned empty DataFrame when all feature values are NaN.
- `uv run pytest tests/test_dbt_integration.py::TestIndicatorMartIntegration::test_indicator_e2e_full_path_persistence_loader_idempotent -q` → GREEN: 1 passed after fixing `vectorbt_loader.py` to handle all-NaN pivot case.
- `uv run pytest tests/test_dbt_integration.py -q` → GREEN: 24 passed (was 23, e2e test now passes).
- `uv run pytest tests/test_indicator_vectorbt_loader.py -q` → GREEN: 9 passed (unchanged).
- `uv run pytest tests/test_indicator_vectorbt_loader.py tests/test_dbt_integration.py -q` → GREEN: 33 passed.
- `uv run ruff check src/funding_backtester/indicators/vectorbt_loader.py` → passed.
- `uv run mypy src/` → passed: 27 source files checked.
