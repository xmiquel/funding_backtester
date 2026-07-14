# Proposal: backtesting-engine

## Intent

Provide a narrow, offline-first deterministic runner for reproducible strategy research. The first slice uses persisted OHLCV features and a single baseline moving-average crossover strategy, with next-bar open execution and persisted metrics plus a trade ledger.

## Scope

### In Scope
- Backend-only deterministic backtest runner over persisted DuckDB data
- Baseline moving-average crossover strategy using persisted features
- Next-bar open execution with explicit cost/slippage assumptions
- Persisted run summary metrics and individual trade ledger rows

### Out of Scope
- HTTP run execution
- Frontend results UI
- Genetic optimization
- Broad strategy catalog or arbitrary strategy authoring

## Capabilities

### New Capabilities
- `backtesting-engine`: offline deterministic runner, baseline strategy execution, run persistence, and trade-ledger storage

### Modified Capabilities
- None

## Approach

Reuse the existing persisted feature/price pipeline as the input contract. Add a backend runner (module or CLI) that loads aligned OHLCV + features, executes the baseline strategy deterministically, records metrics, and writes run/trade results to DuckDB for later read-only consumption.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/funding_backtester/backtesting/` | New | Runner, strategy, execution, and persistence model |
| `backend/tests/` | New/Modified | Determinism, ledger, and metric golden tests |
| `openspec/changes/backtesting-engine/proposal.md` | New | Proposal artifact |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Feature/price misalignment breaks determinism | Medium | Reuse existing aligned loaders and pin golden fixtures |
| Run schema grows too fast | Medium | Start with minimal versioned summary + trade ledger |
| Library numeric drift changes metrics | Medium | Freeze assumptions in tests and document execution rules |

## Rollback Plan

Remove the new backtesting module and any new backtest tables/artifacts; existing feature and OHLCV pipelines remain unchanged.

## Dependencies

- Existing persisted OHLCV and feature layers
- DuckDB-backed storage already used by the project

## Success Criteria

- [ ] A seeded baseline run produces identical metrics and trade rows across repeated executions
- [ ] Run summary and trade ledger are persisted and readable without introducing HTTP or UI dependencies
