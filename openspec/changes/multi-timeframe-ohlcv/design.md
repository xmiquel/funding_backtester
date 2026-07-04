# Design: Multi-Timeframe OHLCV

## Technical Approach

Extend the existing OHLCV pipeline from 15s-only to 8 coarse granularities (1m/3m/5m/15m/1h/3h/4h/1d) via a single dbt macro, chained incremental models, and one new API parameter. Zero schema changes — `OHLCVBar` stays untouched.

## Architecture Decisions

### Decision: Single Macro vs 8 Copies

| Option | Tradeoff | Decision |
|--------|----------|----------|
| 8 model files with inline SQL | Duplicated CTE; drift risk | **Rejected** |
| One macro with parameters | DRY; single source of truth for OHLCV logic | **Chosen** |

**Rationale**: The 15s model has 31 lines. 8 copies × 31 = 248 lines of nearly identical SQL. One macro generates ~15 lines of SQL per call. Macros are dbt-native — no Python, no Jinja spaghetti in every file.

### Decision: Chain from `ohlcv_15s` vs Raw Ticks

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Every model from `dt_tick_data` | N scans of the raw table; identical aggregation 8× | **Rejected** |
| Chain from `ohlcv_15s` | Single aggregation saved; coarse models resample compact bars | **Chosen** |

**Rationale**: `ohlcv_15s` is already materialized as a table. Reading 15s bars vs raw ticks means ~96× fewer rows for daily aggregation. The aggregation is exact — OHLCV is lossless when resampling from finer bars (open=first of first, close=last of last, min/max of mins/maxes is semantically correct).

### Decision: Dynamic Table Name vs 8 Endpoints

| Option | Tradeoff | Decision |
|--------|----------|----------|
| 8 endpoints (`/ohlcv/1m`, `/ohlcv/1d`, etc.) | Discovery surface ×8; no routing changes | **Rejected** |
| One endpoint + `?granularity=` | Single discovery URL; one router registration; backward compat | **Chosen** |

**Rationale**: The existing endpoint already queries a DuckDB table directly. The only change is which table name goes into the SQL. A validated allow-list (`{"15s", "1m", ...}`) prevents injection and makes adding granularities a one-line config change.

## Data Flow

```
Raw ticks (dt_tick_data)
    │
    ▼
ohlcv_15s (incremental, existing)  ◄── unchanged
    │
    ├──► ohlcv_1m  (incremental, new — 2× lookback)
    ├──► ohlcv_3m  (incremental, new)
    ├──► ohlcv_5m  (incremental, new)
    ├──► ohlcv_15m (incremental, new)
    ├──► ohlcv_1h  (incremental, new)
    ├──► ohlcv_3h  (incremental, new)
    ├──► ohlcv_4h  (incremental, new)
    └──► ohlcv_1d  (incremental, new — date_trunc alignment)

API: GET /api/v1/ohlcv?symbol=X&granularity=1m
    └─► map granularity → table name "ohlcv_1m"
    └─► validated allow-list → 422 if invalid
    └─► DuckDB query on dynamic table
    └─► OHLCVBar[] response (identical schema)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `analytics/macros/ohlcv_aggregate.sql` | Create | Shared OHLCV aggregation macro — bucket alignment + window functions + SELECT |
| `analytics/models/marts/ohlcv_1m.sql` | Create | 1-minute bars from `ohlcv_15s` via macro |
| `analytics/models/marts/ohlcv_3m.sql` | Create | 3-minute bars |
| `analytics/models/marts/ohlcv_5m.sql` | Create | 5-minute bars |
| `analytics/models/marts/ohlcv_15m.sql` | Create | 15-minute bars |
| `analytics/models/marts/ohlcv_1h.sql` | Create | 1-hour bars |
| `analytics/models/marts/ohlcv_3h.sql` | Create | 3-hour bars |
| `analytics/models/marts/ohlcv_4h.sql` | Create | 4-hour bars |
| `analytics/models/marts/ohlcv_1d.sql` | Create | Daily bars — `is_daily=true`, `date_trunc` alignment |
| `analytics/models/marts/schema.yml` | Modify | Add entries for all 8 new models + macro docs |
| `backend/src/funding_backtester/api/v1/ohlcv.py` | Modify | Add `granularity` param, dynamic table lookup, allow-list validation |
| `backend/tests/test_ohlcv.py` | Expand | Parametrized integration tests across granularities |

## Interfaces / Contracts

### dbt Macro: `ohlcv_aggregate(bucket_seconds, source_ref, is_daily)`

```sql
{% macro ohlcv_aggregate(bucket_seconds, source_ref, is_daily=false) %}

{% if is_daily %}
    {% set bucket_expr -%}
        date_trunc('day', datetime)
    {%- endset %}
{% else %}
    {% set bucket_expr -%}
        date_trunc('second', datetime)
          - INTERVAL (EXTRACT(SECOND FROM datetime) % {{ bucket_seconds }}) SECOND
    {%- endset %}
{% endif %}

{% set lookback = bucket_seconds * 2 %}

WITH bucketed AS (
    SELECT
        {{ bucket_expr }} AS datetime,
        symbol,
        open, high, low, close, volume,
        bid_open, bid_high, bid_low, bid_close,
        ask_open, ask_high, ask_low, ask_close,
        ROW_NUMBER() OVER (
            PARTITION BY symbol, {{ bucket_expr }}
            ORDER BY datetime ASC
        ) AS rn_asc,
        ROW_NUMBER() OVER (
            PARTITION BY symbol, {{ bucket_expr }}
            ORDER BY datetime DESC
        ) AS rn_desc
    FROM {{ source_ref }}
    {% if is_incremental() %}
    WHERE datetime > (
        SELECT COALESCE(MAX(datetime), '2000-01-01') FROM {{ this }}
    ) - INTERVAL '{{ lookback }} seconds'
    {% endif %}
)
SELECT
    datetime, symbol,
    MAX(CASE WHEN rn_asc = 1 THEN open END) AS open,
    MAX(high) AS high,
    MIN(low) AS low,
    MAX(CASE WHEN rn_desc = 1 THEN close END) AS close,
    SUM(volume) AS volume,
    MAX(CASE WHEN rn_asc = 1 THEN bid_open END) AS bid_open,
    MAX(bid_high) AS bid_high,
    MIN(bid_low) AS bid_low,
    MAX(CASE WHEN rn_desc = 1 THEN bid_close END) AS bid_close,
    MAX(CASE WHEN rn_asc = 1 THEN ask_open END) AS ask_open,
    MAX(ask_high) AS ask_high,
    MIN(ask_low) AS ask_low,
    MAX(CASE WHEN rn_desc = 1 THEN ask_close END) AS ask_close
FROM bucketed
GROUP BY datetime, symbol

{% endmacro %}
```

Naming note: The macro parameter `source_ref` is passed as `ref('ohlcv_15s')` so the ref call is resolved inside each model file, not inside the macro. Each model calls it like:
```sql
{{ ohlcv_aggregate(bucket_seconds=300, source_ref=ref('ohlcv_15s')) }}
```

### API Granularity Contract

```python
VALID_GRANULARITIES: Final[set[str]] = {
    "15s", "1m", "3m", "5m", "15m", "1h", "3h", "4h", "1d"
}

granularity: str = Query("15s", description="OHLCV bar granularity")
# Map: f"ohlcv_{granularity}" → SQL table name
```

### OHLCVBar Schema

Unchanged — the same 15-field model covers all granularities. Granularity is a request param, not a data attribute.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Bucket alignment for sub-daily (EXTRACT % N) | DuckDB in-memory SQL with parametrized bucket sizes |
| Unit | Bucket alignment for daily (date_trunc) | DuckDB in-memory SQL with `is_daily=true` |
| Unit | Macro generates valid SQL for all variants | Compile the macro with dbt (if CI has dbt) or extract SQL pattern |
| Integration | **Row count proportionality**: row counts decrease as granularity coarsens | Same tick data source, query each granularity table |
| Integration | **OHLCV monotonicity**: daily high >= hourly high >= 15m high | Assert price containment across granularities |
| Integration | **Boundary overlap**: incremental build with new data near boundary | Two-pass insert into 15s table, assert no gaps |
| E2E | Backward compat: no granularity → 15s results identical to current | Call without `granularity`, compare to explicit `15s` |
| E2E | Invalid granularity → HTTP 422 | Assert FastAPI validation rejects bad value |
| E2E | Valid granularity returns correct data | Assert table `ohlcv_1m` is queried for `granularity=1m` |

### Test Infrastructure Changes

The `ohlcv_db_path` fixture in `conftest.py` needs to create all granularity tables with derived data, not just `ohlcv_15s`. Two approaches:
1. **Insert 15s data, then derive coarser tables in the fixture**. Preferred — mirrors production chain.
2. **Create each table independently**. Simpler but doesn't validate the chain.

**Approach 1** is chosen. The fixture will create `ohlcv_15s` with sample data, then run the macro's SQL for each granularity to populate the coarser tables.

## Migration / Rollout

No migration required. Coarse models are purely derived from `ohlcv_15s` — no data is moved or transformed. A `dbt build --full-refresh` on first deploy materializes all granularities from existing 15s data.

**Rollback**: Remove the 8 new model files, remove the macro, revert the API endpoint change. Zero data loss — `ohlcv_15s` and `dt_tick_data` are untouched.

## Open Questions

- [ ] Should `ohlcv_1d` use `INTERVAL '2 days'` explicitly (cleaner) or a computed `2 * bucket_seconds` (consistent)? Proposal says 2 days explicitly.
- [ ] Macro path (`analytics/macros/`) doesn't exist yet — confirm `macro-paths: ["macros"]` in `dbt_project.yml` resolves to `analytics/macros/`.
- [ ] The API currently uses DuckDB directly (not dbt-compiled models). Confirm the DuckDB path resolves the same database where dbt materializes tables.
