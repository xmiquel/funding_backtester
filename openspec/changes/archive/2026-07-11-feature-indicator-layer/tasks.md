# Tasks: Feature Indicator Layer

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | Exceeded estimate: `git diff --stat` after this corrective batch observed 1,179 tracked insertions and 22 deletions, plus untracked indicator package/tests/OpenSpec files |
| 400-line budget risk | High |
| Chained PRs recommended | No — maintainer approved a single PR exception |
| Suggested split | Not applied; maintainer accepted `size:exception` for a single PR even though the current diff exceeds the 800-line review budget |
| Delivery strategy | single PR with maintainer-approved `size:exception` |
| Chain strategy | N/A — no chain for this change |

Decision needed before apply: No
Chained PRs recommended: No — maintainer-approved `size:exception`
Chain strategy: N/A
400-line budget risk: High
size:exception: Approved — current observed diff is over the 800-line review budget and must not be represented as budget-compliant.

### Logical Work Units Within Approved Single PR

| Unit | Goal | Review Boundary | Notes |
|------|------|-----------------|-------|
| 1 | Prove installs and bounded catalog | Corrective apply batch | Includes Windows/Ubuntu dependency proof tests. |
| 2 | Persist long-form indicator features | Next apply batch | Adds DuckDB/dbt stage, engine, metadata. |
| 3 | Expose vectorbt loader and smoke checks | Later apply batch | Includes consumer alignment and end-to-end verification. |

## Phase 1: Foundation / Infrastructure

- [x] 1.1 Add `backend/pyproject.toml` dependency pins for `pandas-ta-classic`, `TA-Lib`, and `vectorbt`, then refresh `backend/uv.lock`.
- [x] 1.2 Update `.github/workflows/backend-ci.yml` to prove Windows and Ubuntu install/runtime import paths, including TA-Lib fallback handling.
- [x] 1.3 Create `backend/src/funding_backtester/indicators/parameters.py` with the bounded SMA/EMA/RSI/MACD/ATR/BBANDS catalog and canonical hash helpers.

## Phase 2: Core Implementation

- [x] 2.1 Create `backend/src/funding_backtester/indicators/registry.py` to validate catalog-only requests and expose indicator metadata/output names.
- [x] 2.2 Complete `backend/src/funding_backtester/indicators/engine.py` real-engine proof: existing file is scaffolding/partial implementation only until pandas/pandas-ta-classic/TA-Lib-backed OHLCV DataFrame computation and backend metadata are proven.
- [x] 2.3 Create `backend/src/funding_backtester/indicators/duckdb_io.py` plus `analytics/models/marts/indicator_features.sql` for staged persistence and idempotent dbt materialization.
- [x] 2.4 Add `backend/scripts/build_indicator_features.py` to run local/CI feature builds from DuckDB sources.

## Phase 3: Integration / Wiring

- [x] 3.1 Create `backend/src/funding_backtester/indicators/vectorbt_loader.py` to return aligned close/features Series/DataFrames for vectorbt.
- [x] 3.2 Update `analytics/models/marts/schema.yml` and any dbt references so feature keys, hashes, and reproducibility columns are constrained.
- [x] 3.3 Wire backend/dbt consumers so persisted features are discoverable without exposing indicator internals.

## Phase 4: Testing / Verification

- [x] 4.1 Add `backend/tests/test_indicator_dependencies.py` for Windows/Ubuntu import/version proof and TA-Lib availability assertions.
- [x] 4.2 Add `backend/tests/test_indicator_parameters.py` for catalog bounds, deterministic hashes, and rejection of free-form parameters.
- [x] 4.3 Complete `backend/tests/test_indicator_engine.py` real-engine proof: existing tests are scaffolding/partial coverage only until golden pandas fixtures, backend metadata, and insufficient-lookback behavior prove the production engine.
- [x] 4.4 Extend `backend/tests/test_dbt_integration.py` to verify stage build, dbt persistence, idempotency, and vectorbt-aligned output.

## Phase 5: Cleanup / Documentation

- [x] 5.1 Document the feature mart contract, dependency proof steps, and fallback installation notes where backend/dbt docs live.
- [x] 5.2 Remove any temporary scaffolding after tests pass and confirm the final artifact set matches the design.
