# Design: Feature Indicator Layer

## Technical Approach

Add a bounded Python indicator boundary under `backend/src/funding_backtester/indicators/`. It reads existing OHLCV dbt marts from DuckDB, validates requested features against a committed parameter catalog, computes with `pandas-ta-classic` plus TA-Lib availability metadata, writes `indicator_feature_stage`, and lets dbt materialize `indicator_features`. Persisted features stay long-form and deterministic so vectorbt can pivot them today and future genetic search can reuse identities without free-form parameter generation.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| TA-Lib install path | First use normal `uv` resolution for `TA-Lib` on Python 3.12 and prove `import talib` plus version in pytest/CI. | Start with manual native installs. | TA-Lib Python publishes binary wheels for Linux/macOS/Windows on Python 3.9-3.14, so resolver-first is simplest and reproducible. |
| TA-Lib fallback | Preferred path stays standard resolver/wheel resolution first. If it fails on local Windows Python 3.12, use the confirmed local fallback wheel `D:\repos\ta_lib-0.6.8-cp312-cp312-win_amd64.whl`. Ubuntu CI also tries standard wheels first, then installs/builds the underlying TA-Lib C library before retrying dependency sync. | Make TA-Lib optional or start with manual native installs. | The spec requires proof of availability while keeping the exact confirmed Windows recovery path and a CI-native Ubuntu recovery path. |
| Parameter design | Create `parameters.py` as the bounded SMA/EMA/RSI/MACD/ATR/BBANDS search-space catalog. | Hardcoded defaults inside the engine. | Parameters are future optimizer inputs, not incidental defaults. A catalog enables validation, review, and deterministic reuse. |
| Feature identity | Canonical JSON (`sort_keys=True`, compact separators) plus SHA-256 parameter hash and `feature_id`. | Raw dict serialization or random IDs. | Stable identity lets vectorbt and future genetic search reference persisted features safely. |
| Persistence shape | Long-form `indicator_features` plus Pandas pivot loader. | Wide feature tables. | Long-form supports multi-output indicators and bounded catalog growth without schema churn. |

## Data Flow

```text
OHLCV dbt marts -> catalog validation -> pandas-ta-classic/TA-Lib engine
     -> DuckDB indicator_feature_stage -> dbt indicator_features
     -> vectorbt_loader returns aligned close/features DataFrames
```

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/pyproject.toml`, `backend/uv.lock` | Modify | Add `pandas-ta-classic`, `TA-Lib`, `vectorbt`; standard resolver first. |
| `.github/workflows/backend-ci.yml` | Modify | Local workflow exists and must run dependency proof plus fallback steps if needed. |
| `backend/src/funding_backtester/indicators/parameters.py` | Create | Bounded catalog/search space, canonical JSON, `parameter_hash`, `feature_id`. |
| `backend/src/funding_backtester/indicators/registry.py` | Create | Indicator metadata, output names, catalog-only validation errors. |
| `backend/src/funding_backtester/indicators/engine.py` | Create | Compute SMA, EMA, RSI, MACD, ATR, BBANDS from OHLCV DataFrames. |
| `backend/src/funding_backtester/indicators/duckdb_io.py` | Create | Read OHLCV marts and stage feature rows. |
| `backend/src/funding_backtester/indicators/vectorbt_loader.py` | Create | Pivot persisted features into datetime-aligned vectorbt inputs. |
| `backend/scripts/build_indicator_features.py` | Create | CLI entry point for local/CI/dbt feature builds. |
| `analytics/models/marts/indicator_features.sql` | Create | Final dbt mart with uniqueness/idempotency contract. |
| `analytics/models/marts/schema.yml` | Modify | Document/test non-null keys and metadata columns. |
| `backend/tests/test_indicator_dependencies.py` | Create | Import/version proof for TA-Lib, pandas-ta-classic, vectorbt. |
| `backend/tests/test_indicator_parameters.py` | Create | Bounded catalog, canonical JSON/hash stability, unsupported parameter rejection. |
| `backend/tests/test_indicator_engine.py` | Create | Golden fixtures, TA-Lib metadata, insufficient-lookback behavior. |
| `backend/tests/test_dbt_integration.py` | Modify | Build stage before dbt model and assert persistence/idempotency. |

## Interfaces / Contracts

`parameters.py` exposes catalog entries like `{feature_name, params, outputs, min_lookback}`. Canonical identity input:

```text
source_model, symbol, timeframe, feature_name, canonical_parameter_json, computation_version
```

`indicator_features` columns: `datetime, symbol, timeframe, source_model, feature_name, feature_id, parameter_hash, parameter_json, output_name, value, computed_at, computation_version, pandas_ta_classic_version, talib_available, talib_version, talib_used`.

Uniqueness: `(datetime, symbol, timeframe, source_model, feature_id, output_name)`. `vectorbt_loader.load_features(...)` returns sorted `(close: pd.Series, features: pd.DataFrame)` with columns `{feature_name}_{output_name}_{parameter_hash}`.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Dependency | Windows/Linux install proof | `uv sync`; pytest imports and records versions. Windows local wheel and Ubuntu C-library fallback activate only after standard resolution fails. |
| Unit | Catalog bounds and identity | Stable canonical JSON/hash, deterministic errors for free-form params. |
| Unit | Indicator values | Golden fixtures for supported indicators and metadata capture. |
| Integration | DuckDB/dbt persistence | Extend temp DuckDB `test_dbt_integration.py`; assert idempotent reruns. |
| Consumer | vectorbt contract | Build aligned Series/DataFrames and minimal `Portfolio.from_signals` smoke test. |

## Migration / Rollout

No migration required. Roll out as dependency proof, catalog/engine tests, DuckDB staging, dbt mart, then vectorbt loader. Rollback removes new dependencies, indicator package, dbt model, tests, and CI additions without touching OHLCV marts.

## Open Questions

None.
