# Proposal: NinjaTrader Tick Data Pipeline

## Intent

Ingest NinjaTrader futures tick exports into DuckDB with a maintainable dbt-based pipeline — raw view over TXT files → staging normalization → final materialized table with derived analytical columns — enabling fast backtesting queries without polluting the application PostgreSQL database.

## Scope

### In Scope
- Raw TXT file ingestion into DuckDB via a dedicated Python loader script
- dbt source declaration over the raw file layer
- Staging view deriving `symbol` from filename and `event_ts` from raw timestamp parts
- Final materialized table `dt_tick_data` with derived columns (`spread`, `mid`, `is_aggressive_buy`, `is_aggressive_sell`)
- Audit manifest tracking which source files were loaded per materialization run
- `.gitignore` update to exclude `data/`
- `duckdb` dependency added to `backend/pyproject.toml`

### Out of Scope
- Historical backtesting queries or dashboards consuming the data
- Real-time or streaming tick ingestion
- Non-NinjaTrader tick data sources
- PostgreSQL-based tick storage (DuckDB is the analytical store)
- E2E tests for the pipeline (unit + integration only)

## Capabilities

### New Capabilities
- `tick-data-pipeline`: End-to-end ingestion pipeline for NinjaTrader futures tick data — raw file loading, dbt source/staging/final modeling, derived-column computation, and audit manifest tracking.

### Modified Capabilities
- None

## Approach

1. Add `duckdb>=1.0.0` to `backend/pyproject.toml` and update `.gitignore` to exclude `data/`.
2. Create `backend/scripts/load_ticks.py` — CLI script accepting `<filename> <symbol>`, parsing NT8 Tick Replay format, batching 100K rows via DuckDB DataFrame registration + `INSERT OR IGNORE`.
3. Set up DuckDB database at `data/ticks.duckdb` with a raw view over TXT files exposing raw fields plus filename.
4. Declare the raw layer as a dbt source.
5. Create a staging dbt model normalizing raw fields — derive `symbol` from filename, build `event_ts` from date/time/subsec.
6. Create a final materialized dbt model `dt_tick_data` with derived columns: `spread = ask - bid`, `mid = (bid + ask) / 2`, `is_aggressive_buy = last >= ask`, `is_aggressive_sell = last <= bid`.
7. Add an audit manifest table (`tick_load_manifest`) recording which files were loaded and when.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/pyproject.toml` | Modified | Add `duckdb>=1.0.0` |
| `.gitignore` | Modified | Add `data/` |
| `backend/scripts/load_ticks.py` | New | CLI tick loader |
| `data/ticks.duckdb` | New | DuckDB analytical database |
| `models/` (dbt project) | New | dbt source, staging, final models |
| DuckDB raw view | New | View over TXT files with filename passthrough |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| DuckDB ON CONFLICT batch limitation | High | Use DataFrame registration + INSERT OR IGNORE SELECT |
| Extremely large files causing OOM | Med | 100K-row batch processing |
| dbt-duckdb adapter compatibility | Low | Pin compatible versions in pyproject.toml |
| Source format changes | Low | First-line validation before batch processing |

## Rollback Plan

Remove `duckdb>=1.0.0` from `pyproject.toml`, delete `data/` directory and DuckDB database, delete `backend/scripts/load_ticks.py`, revert `.gitignore`, drop any dbt models added for the pipeline.

## Dependencies

- `duckdb>=1.0.0` Python package
- `dbt-duckdb` adapter for dbt-DuckDB integration
- DuckDB `read_csv_auto` with filename passthrough
- NinjaTrader Tick Replay format (.txt exports)

## Success Criteria

- [ ] `python load_ticks.py <file> <symbol>` parses a sample NT8 export and inserts rows with zero data loss
- [ ] `dbt build` runs the full source → staging → final DAG without errors
- [ ] Final `dt_tick_data` contains correct derived columns (spread, mid, aggressive flags)
- [ ] Duplicate rows are silently skipped via INSERT OR IGNORE
- [ ] Audit manifest records each successful file load with timestamp
- [ ] `data/` is gitignored and never tracked
