# Tasks: backtesting-engine

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 650-900 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: contracts + pure engine + unit tests; PR 2: DuckDB I/O + marts + integration tests; PR 3: CLI wiring + verification/docs |
| Delivery strategy | auto-forecast |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | RED/GREEN for engine contracts and MA crossover core | PR 1 | Base: feature/tracker branch; unit tests first |
| 2 | DuckDB stage-to-mart persistence and schema docs | PR 2 | Base: PR 1 branch; temp DuckDB integration tests |
| 3 | CLI wiring and offline verification | PR 3 | Base: PR 2 branch; same-symbol deterministic run |

## Phase 1: RED — contracts and engine tests

- [ ] 1.1 Add failing tests in `backend/tests/test_backtesting_engine.py` for next-bar-open fills, missing final bar, and negative cost/slippage rejection.
- [ ] 1.2 Add failing tests in `backend/tests/test_backtesting_duckdb_io.py` for stage-to-mart writes, `run_id` linkage, and versioned reruns.
- [ ] 1.3 Add failing CLI/schema tests for `backend/src/funding_backtester/scripts/run_backtest.py` argument validation and unsupported strategy errors.

## Phase 2: GREEN — backtesting core

- [ ] 2.1 Create `backend/src/funding_backtester/backtesting/contracts.py` with run, trade, metadata, and validation error contracts.
- [ ] 2.2 Create `backend/src/funding_backtester/backtesting/strategy.py` and `engine.py` for MA crossover signals and deterministic next-bar-open execution.
- [ ] 2.3 Add `backend/src/funding_backtester/backtesting/__init__.py` exports and `backend/src/funding_backtester/schemas/backtesting.py` for typed CLI/persistence payloads.

## Phase 3: Integration / Wiring

- [ ] 3.1 Create `backend/src/funding_backtester/backtesting/duckdb_io.py` to read the one-symbol OHLCV snapshot and write stage run/trade rows.
- [ ] 3.2 Add `backend/src/funding_backtester/scripts/run_backtest.py` to wire config parsing, execution, and persistence.
- [ ] 3.3 Add `analytics/models/marts/backtest_run_summary.sql`, `backtest_trade_ledger.sql`, and `analytics/models/marts/schema.yml` entries.

## Phase 4: Testing / Verification

- [ ] 4.1 Make `backend/tests/test_backtesting_engine.py` pass against small deterministic fixtures.
- [ ] 4.2 Make `backend/tests/test_backtesting_duckdb_io.py` pass with a temp DuckDB database and rerun assertions.
- [ ] 4.3 Verify CLI and dbt marts together with an offline snapshot run using the same symbol/timeframe.

## Phase 5: Cleanup

- [ ] 5.1 Update `backend/src/funding_backtester/backtesting/__init__.py` and script docstrings with supported scope and limits.
- [ ] 5.2 Remove temporary fixture helpers or debug prints after tests pass.
