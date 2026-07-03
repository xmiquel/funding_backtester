# Design: NinjaTrader Tick Data Pipeline

## Technical Approach

DuckDB view over raw TXT files → dbt staging view normalizing symbol/timestamp → full-refresh materialized `dt_tick_data` with derived columns. dbt project lives in `analytics/`, connecting to a local DuckDB file. Audit manifest is a second full-refresh table recording which files were processed per successful build. Zero materialized intermediate layers — staging is a view.

## Architecture Decisions

### Decision: dbt project location and structure

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Inside `backend/` | Tight coupling to Python package, blurs API/analytics boundary | **Top-level `analytics/`** — clean separation, independent dbt lifecycle |
| Separate repo | Over-engineered for a single pipeline | ✅ |
| `models/` root | Ambiguous with dbt's own `models/` subdirectory | ❌ |

**Chosen**: `analytics/` with `dbt_project.yml`, `models/source.yml`, `models/staging/stg_tick_data.sql`, `models/marts/dt_tick_data.sql`, `models/marts/tick_load_manifest.sql`.

### Decision: Materialization strategy

| Layer | Materialization | Rationale |
|-------|----------------|-----------|
| Raw source | DuckDB native view via `read_csv_auto` | No storage cost, always reflects current files |
| Staging | dbt view (`materialized='view'`) | Normalizes symbol/timestamp without persisting intermediate data |
| `dt_tick_data` | Full-refresh table (`materialized='table'`) | Derived analytics columns need persistence; full refresh guarantees idempotency without dedup logic |
| `tick_load_manifest` | Full-refresh table with ordering dependency on `dt_tick_data` | Records files present at last successful build; ordering dep prevents writes on failed runs |

### Decision: Deduplication strategy

**Choose**: No per-row dedup logic. Full refresh of `dt_tick_data` on every build guarantees cross-run idempotency by construction — the table is rebuilt from scratch, so no duplicate rows can accumulate. Exact intra-file duplicates (all columns identical) are preserved; NT8 export artifacts at the same microsecond with identical prices are considered genuine tick data, consistent with prior user decisions.

### Decision: event_ts derivation

Parse the composite `raw_timestamp` using DuckDB `strptime` plus interval math:

```sql
strptime(date_part || ' ' || time_part, '%Y%m%d %H%M%S')
    + (CAST(ticks_part AS BIGINT) / 10000000.0) * INTERVAL '1 SECOND'
```

The subsecond field in NT8 exports is .NET ticks (100ns resolution). Dividing by 10M converts to fractional seconds with microsecond precision (DuckDB `TIMESTAMP` default).

## Data Flow

```
data/raw/<symbol>.txt
       │
       ▼  DuckDB read_csv_auto (delim=';', filename passthrough)
┌──────────────────┐
│  raw_ticks view   │  ← DuckDB native view, NOT a dbt model
│  (raw_timestamp,  │
│   bid, ask, last, │
│   volume, filename)│
└────────┬─────────┘
         │  dbt source declaration
         ▼
┌──────────────────────┐
│  stg_tick_data (view) │  ← derives symbol & event_ts
│  symbol, event_ts,   │
│  bid, ask, last, vol │
└────────┬─────────────┘
         │  dbt ref()
         ▼
┌──────────────────────────┐
│  dt_tick_data (table)    │  ← materialized full refresh
│  +spread, +mid,          │
│  +is_aggressive_buy/sell │
└────────┬─────────────────┘
         │  ordering dependency (ref)
         ▼
┌──────────────────────────────┐
│  tick_load_manifest (table)  │  ← full refresh, per-build
│  filename, loaded_at         │
└──────────────────────────────┘
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `analytics/dbt_project.yml` | Create | dbt project config pointing to `data/ticks.duckdb` |
| `analytics/models/source.yml` | Create | Declares DuckDB raw view as dbt source |
| `analytics/models/staging/stg_tick_data.sql` | Create | dbt view normalizing symbol and event_ts |
| `analytics/models/marts/dt_tick_data.sql` | Create | Full-refresh table with derived columns |
| `analytics/models/marts/tick_load_manifest.sql` | Create | Full-refresh audit table, depends on dt_tick_data |
| `backend/pyproject.toml` | Modify | Add `duckdb>=1.0.0` and `dbt-duckdb` |
| `.gitignore` | Verify | `data/` already excluded (confirmed) |
| `backend/scripts/load_ticks.py` | Create | CLI loader: NT8 export → DuckDB raw table (non-dbt path) |

## Interfaces / Contracts

### DuckDB Raw View (non-dbt)

```sql
CREATE OR REPLACE VIEW raw_ticks AS
SELECT * FROM read_csv_auto(
    'data/raw/*.txt',
    delim=';',
    header=false,
    columns={
        'raw_timestamp': 'VARCHAR',
        'bid': 'DOUBLE',
        'ask': 'DOUBLE',
        'last': 'DOUBLE',
        'volume': 'BIGINT'
    },
    filename=true
);
```

Columns: `raw_timestamp VARCHAR`, `bid DOUBLE`, `ask DOUBLE`, `last DOUBLE`, `volume BIGINT`, `filename VARCHAR`.

### Staging View Contract

```sql
SELECT
    SPLIT_PART(REPLACE(filename, '.txt', ''), '\\', -1) AS symbol,
    strptime(SUBSTRING(raw_timestamp, 1, 8) || ' ' || SUBSTRING(raw_timestamp, 10, 6), '%Y%m%d %H%M%S')
        + (CAST(COALESCE(NULLIF(SUBSTRING(raw_timestamp, 17), ''), '0') AS BIGINT) / 10000000.0) * INTERVAL '1 SECOND' AS event_ts,
    bid, ask, last, volume
FROM {{ source('tick_data', 'raw_ticks') }}
```

### Final Table Contract

```sql
SELECT
    *,
    ask - bid AS spread,
    (bid + ask) / 2.0 AS mid,
    last >= ask AS is_aggressive_buy,
    last <= bid AS is_aggressive_sell
FROM {{ ref('stg_tick_data') }}
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `event_ts` derivation | SQL query against raw timestamps with known subsec values |
| Unit | Aggressor boolean logic | Edge cases: last == bid, last == ask, null prices |
| Unit | NT8 file validation | `parse_tick_line()` + `scan_tick_files()` edge cases |
| Integration | Full `dbt build` | Run against committed fixture TXT files in `backend/tests/data/` via `test_dbt_integration.py`, verify `dt_tick_data` row count and derived values |
| Integration | Manifest recording | Verify manifest rows match fixture filenames after successful build |
| Integration | Idempotent re-run | Second `dbt build` produces identical row count |
| Schema | not_null / type expectations | dbt built-in `not_null` and `unique` tests in `schema.yml` co-located with models |

### Integration Test Infrastructure

- **Fixture TXT files**: committed in `backend/tests/data/` (e.g., `MNQ0626.txt`, `ES0626.txt`) — small, reproducible samples in NT8 Tick Replay format.
- **Test harness**: `backend/tests/test_dbt_integration.py` — pytest fixtures create a temporary DuckDB, bootstrap the `raw_ticks` view over fixture files, run `dbt build` via subprocess, then verify outputs via DuckDB SQL queries.
- **CI**: Separate `dbt-integration` job in `.github/workflows/backend-ci.yml` — runs after `quality` passes, does not wait for the main `test` job.
- **Schema expectations**: `analytics/models/staging/schema.yml` and `analytics/models/marts/schema.yml` declare `not_null` and `unique` dbt tests.
- **No `pytest-dbt-duckdb` dependency**: `duckdb==1.2.2` pin conflicts with project's `duckdb==1.5.4`. Using direct DuckDB Python + subprocess `dbt build` pattern instead, which provides equivalent coverage without the version conflict.
- **Directory conventions**: `data/` is gitignored for raw tick exports; `backend/tests/data/` is committed for reproducible test fixtures.

## Migration / Rollout

No data migration required — this is net-new infrastructure. First run creates the DuckDB database at `data/ticks.duckdb`, creates the raw view, and runs `dbt build`. No zero-downtime requirement since DuckDB is read by backtesting queries only.

## Open Questions

- [ ] `dbt-duckdb` adapter: confirm connection config for local file path and schema
- [ ] Loader script (`load_ticks.py`): decide whether it writes to DuckDB raw table or directly produces the DuckDB database that dbt reads — the design assumes a separate raw-table ingest path (non-dbt) to avoid dbt running the CSV scan on every `dbt compile`
