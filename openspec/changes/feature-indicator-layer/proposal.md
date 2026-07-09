# Proposal: Feature Indicator Layer

## Intent

Define persisted OHLCV-derived indicator features for vectorbt backtesting first, while keeping the layer reusable for future AI/model-training.

## Scope

### In Scope
- Use `pandas-ta-classic` as the indicator API, with TA-Lib installed too.
- Design dbt/DuckDB feature outputs fed by existing OHLCV models.
- Shape persisted data for aligned vectorbt Pandas Series/DataFrames.
- Validate a minimal indicator set: SMA, EMA, RSI, MACD, ATR, Bollinger Bands.

### Out of Scope
- Broad indicator-library selection.
- Full vectorbt strategy implementation.
- Model training pipeline implementation.
- Exhaustive indicator catalog.

## Capabilities

### New Capabilities
- `feature-indicator-layer`: Computes, persists, and exposes reusable OHLCV indicator features.

### Modified Capabilities
- None. `ohlcv-aggregation` remains the upstream data source contract.

## Approach

Adopt `pandas-ta-classic`: it extends Pandas via `df.ta.*`, supports the first indicators, and can append vectorbt-friendly columns. Install TA-Lib too because `pandas-ta-classic` may use TA-Lib-backed implementations, and TA-Lib helps performance/compatibility.

Implement dbt/DuckDB feature tables over OHLCV, with Python only at the indicator boundary. Persist symbol, timeframe, source OHLCV model, datetime, feature name, parameter set, values, computed timestamp, `pandas-ta-classic` version, TA-Lib version/availability, and whether TA-Lib-backed execution was used.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `openspec/specs/feature-indicator-layer/spec.md` | New | Feature capability contract. |
| `analytics/models/` | New | Derived feature tables/models over OHLCV. |
| `backend/` | Modified | Optional read/query integration after shape proof. |
| `pyproject.toml` / CI | Modified | Add/prove dependencies and vectorbt-facing shape. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| TA-Lib install friction on Windows/Python 3.12+ | High | Prove CI/local install; local wheels in `D:\repos` cover 3.11/3.13, but project standard is 3.12+. |
| Native vs TA-Lib-backed differences | Med | Add golden fixtures and persist backend metadata. |
| Overbuilding for AI before backtesting proof | Med | Validate backtesting workflows first with reusable metadata. |
| dbt/DuckDB/Python boundary complexity | Med | Keep persistence in dbt/DuckDB and isolate Python library calls. |

## Rollback Plan

Remove feature dbt models/tables, dependency additions, and optional backend query endpoints. Existing tick/OHLCV specs and data remain unchanged.

## Dependencies

- `ohlcv-aggregation` and DuckDB/dbt pipeline.
- `pandas-ta-classic` as the indicator API.
- TA-Lib installed and available where compatible.
- vectorbt as the backtesting consumer target.
- Python 3.12+ compatible local/CI install path.

## Success Criteria

- [ ] Dependency proof covers `pandas-ta-classic`, TA-Lib availability/version, and vectorbt-facing persisted data shape.
- [ ] Minimal indicators can be computed reproducibly from OHLCV data.
- [ ] Feature values persist with reproducibility and execution-backend metadata.
- [ ] vectorbt can consume aligned persisted features without duplicating computation logic.
