# Design: backtesting-engine

## Technical Approach

Build a backend-only backtesting boundary under `backend/src/funding_backtester/backtesting/` that mirrors the existing indicators pattern: a pure strategy/execution core, a DuckDB I/O boundary, and a thin CLI entrypoint. The runner reuses the same DuckDB-aligned data contract shape as `indicators/vectorbt_loader.load_features()`, computes a single moving-average crossover strategy, evaluates signals on bar close, fills on the next bar open, applies explicit commission/slippage deterministically, and persists versioned run outputs to DuckDB. This design intentionally excludes HTTP execution, UI, optimization, and strategy catalog expansion.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Boundary shape | Add `backtesting/engine.py`, `strategy.py`, `duckdb_io.py`, and `contracts.py` plus a CLI script. | One monolithic script. | Matches the existing indicators boundary style, keeps execution pure, and makes unit/integration testing cheap. |
| Execution model | Use a deterministic event loop over ordered OHLCV bars with next-bar open fills. | Vectorbt portfolio simulation as the primary engine. | The spec requires next-bar-open semantics and explicit cost/slippage behavior with no hidden simulator assumptions. |
| Persistence model | Write versioned DuckDB stage tables for run summaries/trades, then expose final marts through dbt models. | Overwrite a single results table or store only JSON blobs. | Versioned tables preserve reruns, auditing, and reproducibility while staying consistent with the existing stage→mart pattern. |
| Strategy scope | Hardcode one strategy version: moving-average crossover (`ma-crossover-v1`). | Free-form strategy catalog or optimizer. | The change is intentionally narrow; free-form strategies would weaken determinism and expand review scope. |

## Data Flow

```text
DuckDB ohlcv_15s
  → backtesting.duckdb_io.load_backtest_inputs
  → backtesting.strategy.build_signal_frame
  → backtesting.engine.execute_next_bar_open
  → backtesting.duckdb_io.write_run_stage / write_trade_stage
  → dbt marts: backtest_run_summary, backtest_trade_ledger
```

The runner reads one symbol/timeframe snapshot, derives fast/slow moving averages from ordered closes, emits a signal on bar close, and records fills only when bar N+1 exists. Run metadata includes snapshot identity, code revision, strategy version, parameters, and a schema version.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/src/funding_backtester/backtesting/__init__.py` | Create | Package export for the backtesting boundary. |
| `backend/src/funding_backtester/backtesting/contracts.py` | Create | Typed run, trade, metadata, and error contracts. |
| `backend/src/funding_backtester/backtesting/strategy.py` | Create | Pure moving-average crossover signal generation. |
| `backend/src/funding_backtester/backtesting/engine.py` | Create | Deterministic next-bar-open execution and cost/slippage application. |
| `backend/src/funding_backtester/backtesting/duckdb_io.py` | Create | Load aligned OHLCV inputs and persist stage rows to DuckDB. |
| `backend/src/funding_backtester/scripts/run_backtest.py` | Create | Offline CLI entrypoint mirroring existing script conventions. |
| `backend/src/funding_backtester/schemas/backtesting.py` | Create | Optional response/row models for typed persistence and CLI output. |
| `analytics/models/marts/backtest_run_summary.sql` | Create | Final mart for versioned run summaries from the stage table. |
| `analytics/models/marts/backtest_trade_ledger.sql` | Create | Final mart for trade ledger rows from the stage table. |
| `analytics/models/marts/schema.yml` | Modify | Document and test the new backtest marts. |
| `backend/tests/test_backtesting_engine.py` | Create | Determinism, fill timing, and cost/slippage tests. |
| `backend/tests/test_backtesting_duckdb_io.py` | Create | DuckDB staging/persistence round-trip tests. |

## Interfaces / Contracts

```python
@dataclass(frozen=True, slots=True)
class BacktestConfig:
    source_model: str
    symbol: str
    timeframe: str
    fast_window: int
    slow_window: int
    commission_bps: Decimal
    slippage_bps: Decimal
    initial_cash: Decimal
    strategy_version: str = "ma-crossover-v1"
```

```python
class BacktestRunSummary(BaseModel):
    run_id: str
    schema_version: str
    strategy_version: str
    input_snapshot_id: str
    code_revision: str
    status: Literal["success", "partial", "failed"]
```

Run rows and trade rows should carry `run_id` so versioned reruns remain linkable.

### Error handling

- `BacktestValidationError`: unsupported strategy, negative costs/slippage, missing required metadata.
- `BacktestDataError`: empty source data, misordered bars, or a signal with no next bar.
- `BacktestPersistenceError`: DuckDB write failures or schema mismatches.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Signal generation, fill timing, fee/slippage math | Pure fixture-driven tests on small OHLCV frames. |
| Integration | DuckDB persistence and versioned reruns | Temp DuckDB database; assert stage rows, final marts, and run linkage. |
| E2E | Offline CLI run | Seed a tiny DuckDB snapshot, run the CLI twice, verify identical outputs. |

## Migration / Rollout

No migration required. Add the new backtesting package and DuckDB marts alongside the existing OHLCV/indicator pipeline. Roll out as backend-only/offline; do not expose HTTP or UI entrypoints. If the stage schema needs adjustment later, version the tables rather than mutating historical rows.

## Open Questions

- [ ] Should the first persistence layer write directly to final marts, or keep explicit `*_stage` tables like the indicator pipeline?
- [ ] Is the initial slice symbol-scoped or batch-scoped across multiple symbols?
