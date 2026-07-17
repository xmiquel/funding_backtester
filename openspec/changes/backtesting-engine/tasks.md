# Tasks: backtesting-engine

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 220-320 |
| 400-line budget risk | Low |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: typed contracts + pure MA signal generation + unit tests; PR 2: execution/fills/run identity/costs + unit tests; PR 3: DuckDB I/O + marts + integration tests; PR 4: CLI wiring + verification/docs |
| Delivery strategy | feature-branch-chain |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | RED/GREEN for typed contracts and pure MA signal core | PR 1 | Base: feature/tracker branch; unit tests first |
| 2 | Next-bar-open execution, fills, identity, and costs | PR 2 | Base: PR 1 branch; deterministic execution tests |
| 3 | DuckDB stage-to-mart persistence and schema docs | PR 3 | Base: PR 2 branch; temp DuckDB integration tests |
| 4 | CLI wiring and offline verification | PR 4 | Base: PR 3 branch; same-symbol deterministic run |

## Phase 1 — contracts and signal tests

- [x] 1.1 Add behavioral tests in `backend/tests/test_backtesting_engine.py` for typed contract validation and MA crossover signal generation.
- [ ] 1.2 Add failing tests in `backend/tests/test_backtesting_duckdb_io.py` for stage-to-mart writes, `run_id` linkage, and versioned reruns.
- [ ] 1.3 Add failing CLI/schema tests for `backend/src/funding_backtester/scripts/run_backtest.py` argument validation and unsupported strategy errors.

## Phase 2: GREEN — backtesting core slice 1

- [x] 2.1 Create `backend/src/funding_backtester/backtesting/contracts.py` with typed config/metadata contracts and validation errors for the signal layer.
- [x] 2.2 Create `backend/src/funding_backtester/backtesting/strategy.py` for pure MA crossover signals.
- [x] 2.3 Add `backend/src/funding_backtester/backtesting/__init__.py` exports for the backtesting core symbols.
- [ ] 2.4 Create `backend/src/funding_backtester/schemas/backtesting.py` for typed CLI/persistence payloads.
- [x] 2.5 Create `backend/src/funding_backtester/backtesting/engine.py` for next-bar-open execution, fills, run identity, and costs (PR 2).

## Phase 3: Integration / Wiring

- [ ] 3.1 Create `backend/src/funding_backtester/backtesting/duckdb_io.py` to read the one-symbol OHLCV snapshot and write stage run/trade rows.
- [ ] 3.2 Add `backend/src/funding_backtester/scripts/run_backtest.py` to wire config parsing, execution, and persistence.
- [ ] 3.3 Add `analytics/models/marts/backtest_run_summary.sql`, `backtest_trade_ledger.sql`, and `analytics/models/marts/schema.yml` entries.

## Phase 4: Testing / Verification

- [x] 4.1 Make `backend/tests/test_backtesting_engine.py` pass against typed-contract and signal-layer fixtures.
- [ ] 4.2 Make `backend/tests/test_backtesting_duckdb_io.py` pass with a temp DuckDB database and rerun assertions.
- [ ] 4.3 Verify CLI and dbt marts together with an offline snapshot run using the same symbol/timeframe.

## Phase 5: Cleanup

- [ ] 5.1 Update `backend/src/funding_backtester/backtesting/__init__.py` and script docstrings with supported scope and limits.
- [ ] 5.2 Remove temporary fixture helpers or debug prints after tests pass.

## PR2 Autonomous Slice: deterministic execution

- [x] PR2.1 Add behavioral tests for next-bar-open fills, missing final bars, deterministic run identity, and cost/slippage effects.
- [x] PR2.2 Implement pure next-bar-open execution with long entry/exit fills and explicit Decimal costs.
- [x] PR2.3 Add immutable run summary, fill, trade, and result contracts with reproducibility metadata linkage.
- [x] PR2.4 Verify the focused engine test suite, Ruff, and mypy; keep DuckDB, marts, CLI, dbt, and frontend out of scope.

## PR1 Reliability Remediation

- [x] R1.1 Add `_validate_decimal` and normalize non-finite Decimal and contract type/value failures to `BacktestValidationError`.
- [x] R1.2 Make `_freeze_parameter_value` reject unsupported mutable parameter values while recursively freezing supported containers.
- [x] R1.3 Add `_validate_temporal_index` and reject non-temporal, unordered, or duplicate signal indexes before calculation.
- [x] R1.4 Cover the remediation behaviors in `backend/tests/test_backtesting_engine.py` and record factual TDD evidence in `apply-progress.md`.

## PR2 Reliability Remediation

- [x] R2.1 Reject bytes, non-string metadata keys, key collisions, and non-finite floats with `BacktestValidationError` before run identity generation.
- [x] R2.2 Validate non-empty, aligned, numeric, finite, non-negative open prices before execution.
- [x] R2.3 Document and test final-position behavior: an open position remains unclosed and is excluded from completed trades.
- [x] R2.4 Document the public execution and exported contract semantics without expanding into CLI or PR4 documentation.

## PR3A1a Slice: Result / Trade Validation

- [x] PR3A1a.1 Add the one-unit `BacktestTrade.quantity` contract.
- [x] PR3A1a.2 Validate independent `BacktestTrade` timestamp, Decimal, linkage, quantity, and PnL invariants.
- [x] PR3A1a.3 Validate `BacktestResult` structure, summary metadata, trade collection, and unfilled-signal count.
- [x] PR3A1a.4 Add independent invariant tests without expanding public `BacktestFill` field validation.
- [x] PR3A1a.5 Run the frozen development environment and focused/full test checks.
