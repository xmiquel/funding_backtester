# Exploration: DuckDB Tick Data for NinjaTrader Futures Exports

## Current State

The project has no tick data infrastructure. No `data/` directory, no DuckDB dependency, no loading scripts. The backend uses PostgreSQL/SQLAlchemy async for application data — completely wrong tool for analytical tick queries.

## NinjaTrader Column Mapping — Confirmed from Official Docs

Source: [NinjaTrader Import Help Guide](https://ninjatrader.com/support/helpguides/nt8/importing.htm) — **Tick Replay Format**

```
yyyyMMdd HHmmss fffffff;last price;bid price;ask price;volume
```

The sample data matches exactly:

```
20260623 140837 4160000;29945;29945;29945.5;1
```

| Col | Value      | Field         | Type    | Notes                                    |
|-----|------------|---------------|---------|------------------------------------------|
| 1   | `20260623` | Date          | DATE    | yyyyMMdd, space-separated from time      |
| 2   | `140837`   | Time          | TIME    | HHmmss, space-separated from subsec      |
| 3   | `4160000`  | Subsec        | INTEGER | 100ns units (10-millionths of a second)  |
| 4   | `29945`    | Last price    | DOUBLE  | After `;` delimiter                      |
| 5   | `29945`    | **Bid** price | DOUBLE  | User was correct — bid before ask        |
| 6   | `29945.5`  | **Ask** price | DOUBLE  |                                           |
| 7   | `1`        | Volume        | INTEGER |                                           |

### Critical findings

- **Column order confirmed**: date → time → subsec → last → **bid** → ask → volume. The user's intuition that bid comes before ask was correct.
- **Delimiter structure**: First 3 fields are space-separated; `;` separates the remaining 4 fields.
- **Sub-sec precision**: 100ns (10-millionths of a second). DuckDB `TIMESTAMP(6)` only supports microsecond precision (1,000ns). Must store separately to preserve full 7-digit precision.
- **Sample data contains exact duplicate rows** — `INSERT OR IGNORE` is essential.
- **File naming convention**: `MNQ 09-26.Last.txt` follows `{Instrument} {YY-MM}.Last.txt`.
- **Time zone**: UTC per NinjaTrader docs.

## Proposed DuckDB Schema

```sql
CREATE TABLE ticks (
    symbol      VARCHAR   NOT NULL,    -- e.g. 'MNQ0926'
    tick_date   DATE      NOT NULL,    -- from yyyyMMdd
    tick_time   TIME      NOT NULL,    -- from HHmmss
    tick_subsec INTEGER   NOT NULL,    -- 100ns units (0-9999999)
    last_price  DOUBLE    NOT NULL,
    bid_price   DOUBLE    NOT NULL,
    ask_price   DOUBLE    NOT NULL,
    volume      INTEGER   NOT NULL,
    PRIMARY KEY (symbol, tick_date, tick_time, tick_subsec)
);
```

### Schema rationale

- **Separate date/time/subsec columns** (not a single TIMESTAMP): preserves full 100ns precision that would be lost in DuckDB's microsecond TIMESTAMP.
- **Composite PK on (symbol, tick_date, tick_time, tick_subsec)**: guarantees idempotent inserts and naturally orders data for time-range queries.
- **All columns NOT NULL**: tick data has no nulls in this format.
- **No surrogate ID**: the natural key is sufficient and more query-friendly.

## Approaches Considered

| # | Approach                         | Pros                                   | Cons                                             | Effort |
|---|----------------------------------|----------------------------------------|--------------------------------------------------|--------|
| 1 | **Separate date/time/subsec**    | Full precision, simple PK, idempotent  | Query needs column concat for time ranges        | Low    |
| 2 | Single `TIMESTAMP(6)`            | Simple queries, built-in time funcs    | Loses 7th digit precision, potential PK collision | Low    |
| 3 | TIMESTAMP + subsec               | Best of both worlds                    | Two time-related columns, ambiguous canonical key | Low    |

**Recommendation: Approach 1**. Preserves all data fidelity. Querying is still straightforward:
```sql
WHERE tick_date >= '2026-06-01'
  AND tick_time BETWEEN '09:30:00' AND '16:00:00'
```

## Load Script Plan

**Script**: `backend/scripts/load_ticks.py`

### CLI Interface
```
python load_ticks.py <filename> <symbol>
```

### Behavior
1. Connect to `data/ticks.duckdb` (auto-creates DB and table if missing)
2. Read file line by line
3. Parse each line:
   - Split by `;` → first token is `"YYYYMMDD HHMMSS fffffff"`
   - Split first token by space → date, time, subsec
   - Remaining 4 tokens → last, bid, ask, volume
4. Batch 100K rows → register as DuckDB relation → `INSERT OR IGNORE INTO ticks SELECT * FROM batch`
5. Report: lines read / inserted / skipped

### Why NOT executemany
DuckDB does not support `ON CONFLICT` with `executemany()` in batch mode. The working pattern is:
- Build batches as list of tuples
- Register as a temporary view via DuckDB Python API
- `INSERT OR IGNORE INTO ticks SELECT * FROM temp_view`

## Risks

| Risk                                           | Mitigation                                                    |
|------------------------------------------------|---------------------------------------------------------------|
| DuckDB batch ON CONFLICT limitation            | Use DataFrame registration + INSERT OR IGNORE SELECT          |
| `data/` committed to git                       | Update `.gitignore` to include `data/` BEFORE creating dir    |
| Extremely large files (100M+ rows)             | Batch in 100K chunks; early prototype with full file first    |
| Source file format changes                     | NT8 format stable for years; validate first line before parse |
| Symbol inference from filename unreliable      | Script takes explicit CLI arg, no filename inference          |
| Missing `duckdb` Python package                | Add to `backend/pyproject.toml` dependencies                  |

## Ready for Proposal

**Yes.** The format is verified against official NinjaTrader documentation, the schema correctly handles the data, and the DuckDB approach is well-suited for analytical tick queries. Recommend moving to `sdd-propose` to formalize the change.
