# ohlcv-aggregation Specification

## Purpose

Compute, store, and serve 15-second OHLCV bars from tick data. Reduces ~153M rows by ~99.9% while preserving last-traded, bid, and ask price structure for backtesting.

## Requirements

### Requirement: Last-Traded OHLCV Aggregation

The system MUST compute open (first tick's `last`), high (max `last`), low (min `last`), close (last tick's `last`), and volume (sum of `volume`) per 15s bucket.

#### Scenario: Standard bucket

- GIVEN tick data for `MNQ0626` on 2026-03-15 spanning several 15s buckets
- WHEN the dbt model processes all ticks
- THEN each bucket's open = first tick's `last`, high = max `last`, low = min `last`, close = last tick's `last`, volume = sum of `volume`
- AND the result matches a manual window-function calculation

#### Scenario: Single-tick bucket

- GIVEN a 15s bucket with exactly one tick
- WHEN processed
- THEN open, high, low, close = that tick's `last` and volume = that tick's `volume`

### Requirement: Bid/Ask OHLCV

The system MUST compute parallel `bid_ohlcv` and `ask_ohlcv` columns using identical logic on `bid` and `ask` price columns.

#### Scenario: Bid and ask mirror last-traded

- GIVEN tick data with `bid` and `ask` columns
- WHEN OHLCV buckets are computed
- THEN `bid_open`/`bid_high`/`bid_low`/`bid_close` and `ask_open`/`ask_high`/`ask_low`/`ask_close` follow the same first/max/min/last logic as last-traded

#### Scenario: Null bid/ask values

- GIVEN a bucket where some ticks have null `bid` or `ask`
- WHEN computing bid/ask OHLCV
- THEN nulls MUST NOT affect min/max/first/last of non-null values in that bucket

### Requirement: 15-Second Bucket Alignment

Bucket `datetime` MUST align to 15-second boundaries with second-precision TIMESTAMP (no fractional seconds). Formula: `date_trunc('second', event_ts) - INTERVAL (EXTRACT(SECOND FROM event_ts) % 15) SECOND`.

#### Scenario: Tick at exact boundary

- GIVEN a tick at `2026-03-15 09:30:00.000`
- WHEN bucketed
- THEN it falls into `2026-03-15 09:30:00`

#### Scenario: Tick near boundary end

- GIVEN a tick at `2026-03-15 09:30:14.999`
- WHEN bucketed
- THEN it falls into `2026-03-15 09:30:00`; next bucket starts at `09:30:15`

### Requirement: Incremental Build

The model MUST use incremental materialization with `unique_key = (datetime, symbol)`, processing only `datetime > COALESCE((SELECT MAX(datetime) FROM ohlcv_15s), '2000-01-01')`.

#### Scenario: Idempotent re-run

- GIVEN `ohlcv_15s` has bars up to `2026-03-15 12:00:00`
- WHEN the model re-runs with no new source data
- THEN zero rows are inserted or updated

#### Scenario: New data

- GIVEN new tick data after the last processed bucket
- WHEN the model runs incrementally
- THEN only newer buckets are computed and inserted

### Requirement: API Query by Symbol

`GET /api/v1/ohlcv` MUST accept `symbol` (required), `start_date` and `end_date` (optional). Results sorted by `(datetime, symbol)` ascending.

#### Scenario: Symbol-only query

- GIVEN bars for `MNQ0626` and `ESU0626`
- WHEN `GET /api/v1/ohlcv?symbol=MNQ0626`
- THEN only `MNQ0626` bars are returned, sorted by datetime ascending

#### Scenario: Filtered by date range

- GIVEN bars spanning multiple days
- WHEN `GET /api/v1/ohlcv?symbol=MNQ0626&start_date=2026-03-15&end_date=2026-03-16`
- THEN bars with `datetime >= 2026-03-15 AND datetime < 2026-03-16` are returned

#### Scenario: Missing symbol

- GIVEN no `symbol` parameter
- WHEN `GET /api/v1/ohlcv`
- THEN HTTP 422 with a Pydantic validation error

### Requirement: API Response Schema

Response MUST be a JSON array of bars with all 15 columns: `datetime`, `symbol`, `open`, `high`, `low`, `close`, `volume`, `bid_open`, `bid_high`, `bid_low`, `bid_close`, `ask_open`, `ask_high`, `ask_low`, `ask_close`.

#### Scenario: Full response shape

- GIVEN valid query params
- WHEN the endpoint returns bars
- THEN every bar has all 15 columns with correct types (datetime as ISO string, prices as float, volume as int)

#### Scenario: Empty result

- GIVEN a symbol with no bars in the requested range
- WHEN the endpoint returns
- THEN the response is `[]`
