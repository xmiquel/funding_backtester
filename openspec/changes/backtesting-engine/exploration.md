## Exploration: backtesting-engine

### Current State
The repository already has the data prerequisites for a deterministic engine: tick ingestion/dbt builds `dt_tick_data` and `ohlcv_15s`, the indicator layer persists bounded features with stable identities/metadata, and `vectorbt_loader.load_features()` already returns aligned close + feature pandas objects from DuckDB. What is missing is an actual backtesting execution boundary, cost/slippage modeling, run-result persistence, and a read path for results.

### Affected Areas
- `backend/src/funding_backtester/indicators/vectorbt_loader.py` — current DuckDB→vectorbt consumer boundary; the new engine should reuse this shape.
- `backend/src/funding_backtester/indicators/duckdb_io.py` / `parameters.py` / `engine.py` — deterministic persisted features and metadata are the input contract.
- `backend/src/funding_backtester/api/v1/ohlcv.py` — source OHLCV query boundary for any server-side engine validation or debugging.
- `backend/src/funding_backtester/api/v1/features.py` — persisted feature discovery/read API that a future engine UI can consume.
- `backend/src/funding_backtester/services/duckdb_client.py` — existing async DuckDB boundary; a read-only results API would likely follow this pattern.
- `backend/tests/test_indicator_vectorbt_loader.py`, `backend/tests/test_indicator_engine.py`, `backend/tests/test_dbt_integration.py` — current deterministic data/feature contracts to preserve.
- `frontend/src/routes/index.tsx` / `frontend/src/api/client.ts` — frontend is currently just a health check; no backtest UX boundary exists yet.

### Approaches
1. **Offline-first deterministic runner** — add a backend/backtesting module or CLI that loads persisted OHLCV + features from DuckDB, runs a baseline strategy, applies explicit costs/slippage, computes reproducible metrics, and persists run/result rows back to DuckDB.
   - Pros: smallest blast radius, easiest to make deterministic, reuses current persistence model, testable without UI.
   - Cons: no immediate interactive UX, needs later read APIs if results should be browsed remotely.
   - Effort: Medium

2. **API-first backtesting service** — expose run/start/result endpoints now and let the backend execute strategy runs on demand.
   - Pros: immediate frontend/API integration path, easier to orchestrate from UI.
   - Cons: larger surface area, harder determinism/reproducibility story, more coupling to async/web concerns.
   - Effort: High

### Recommendation
Start with the offline-first deterministic runner. The narrow first slice should be a single baseline strategy that consumes persisted features from DuckDB, models execution costs/slippage explicitly, emits reproducible metrics, and writes persisted run results. After that slice is proven, add thin read-only APIs and then frontend presentation.

### Risks
- The current codebase has no established run-results schema, so the first persistence model must be intentionally minimal and versioned.
- Feature/price alignment is already strict in the loader; the engine must preserve timestamp alignment or deterministic metrics will drift.
- Vectorbt/numeric library behavior can vary across dependency versions, so golden tests must pin the expected metric output for seeded fixtures.

### Ready for Proposal
Yes — the next step should be a proposal/spec for a minimal deterministic backtesting engine slice with persisted run results and a clear no-go list for strategy breadth.
