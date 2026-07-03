# Tick Data Pipeline Specification

## Purpose

End-to-end ingestion for NinjaTrader futures tick exports: raw TXT files discovered via DuckDB filename passthrough → dbt staging view normalizing `symbol` and `event_ts` → final materialized `dt_tick_data` with derived analytical columns → audit manifest tracking load runs.

## Requirements

### Requirement: Raw Source File Layout

Raw tick exports MUST reside in `data/raw/` named `<symbol>.txt`. The `data/` directory MUST be gitignored. Raw source files MUST NOT be deleted or modified during ingestion.

#### Scenario: File discovered and preserved

- GIVEN `data/raw/MNQ0626.txt` exists
- WHEN the pipeline runs
- THEN the file is discovered and remains unmodified

#### Scenario: Empty source directory

- GIVEN `data/raw/` contains no files
- WHEN the pipeline runs
- THEN it reports an empty-source condition without raising an unhandled error

### Requirement: Raw DuckDB View

Raw tick files MUST be exposed via a DuckDB view (not materialized) using filename-passthrough. The view MUST expose all raw TXT columns plus the originating filename.

#### Scenario: View serves file content

- GIVEN one or more TXT files exist in `data/raw/`
- WHEN the raw view is queried
- THEN every row exposes a `filename` column and all raw columns from the source file

#### Scenario: Parse error on format mismatch

- GIVEN a file in `data/raw/` does not match the expected NinjaTrader Tick Replay column layout
- WHEN DuckDB attempts to parse it via the raw view
- THEN the system surfaces a readable parse error

### Requirement: Staging View Normalization

A dbt staging view (not materialized) MUST derive `symbol` from the raw filename (stem before `.txt`). It MUST derive `event_ts` by combining the raw date, time, and subsecond parts into a single TIMESTAMP column.

#### Scenario: Symbol and event_ts derived

- GIVEN a raw row with `filename = 'MNQ0626.txt'`, date `2026-03-15`, time `09:30:01`, subsec `123`
- WHEN the staging view processes this row
- THEN `symbol` resolves to `MNQ0626`
- AND `event_ts` resolves to `2026-03-15 09:30:01.123`

#### Scenario: Null subsecond handling

- GIVEN a raw row with null or missing subsecond
- WHEN the staging view processes this row
- THEN `event_ts` is produced with subsecond set to zero (no crash)

### Requirement: Materialized Tick Data Table

The system MUST materialize `dt_tick_data` from the staging view with computed columns: `spread = ask - bid`, `mid = (bid + ask) / 2`, `is_aggressive_buy = last >= ask`, `is_aggressive_sell = last <= bid`. This model MUST be materialized as a table (not a view).

#### Scenario: Derived columns computed correctly

- GIVEN a staging row with bid = 4500.25, ask = 4500.50, last = 4500.50
- WHEN `dt_tick_data` materializes
- THEN `spread` = 0.25, `mid` = 4500.375, `is_aggressive_buy` = true, `is_aggressive_sell` = false

#### Scenario: Aggressive sell at bid boundary

- GIVEN a staging row with bid = 4500.25, ask = 4500.50, last = 4500.25
- WHEN `dt_tick_data` materializes
- THEN `is_aggressive_sell` = true (last <= bid)
- AND `is_aggressive_buy` = false

### Requirement: Duplicate Handling

Duplicate rows MUST be silently skipped during materialization. Raw source files MUST NOT be deleted or archived after load — re-running the pipeline against previously loaded files MUST be idempotent.

#### Scenario: Idempotent re-run

- GIVEN a source file whose rows are already present in `dt_tick_data`
- WHEN the pipeline runs again
- THEN no duplicate rows appear in `dt_tick_data`
- AND the run completes without error

### Requirement: Load Audit Manifest

The system MUST maintain an audit table `tick_load_manifest` that records each successful materialization run: which source files were loaded and the run timestamp. Failed or interrupted runs MUST NOT be recorded.

#### Scenario: Successful run recorded

- GIVEN a successful `dbt build` that includes `MNQ0626.txt`
- WHEN the run completes
- THEN `tick_load_manifest` contains a row with `filename = 'MNQ0626.txt'` and a non-null run timestamp

#### Scenario: Failed run omitted

- GIVEN a dbt build fails during the materialization step
- WHEN the run does not complete successfully
- THEN `tick_load_manifest` MUST NOT contain a row for that run
