# Delta for ohlcv-aggregation

## ADDED Requirements

### Requirement: Aggregation Macro

A `ohlcv_aggregate(bucket_seconds, source_ref, is_daily)` macro MUST generate OHLCV aggregation SQL reusable across granularities. Sub-daily SHALL use `EXTRACT(SECOND from dt) % bucket_seconds` for alignment. Daily (`is_daily=true`) SHALL use `date_trunc('day', datetime)` for calendar-midnight boundaries.

#### Scenario: 1m aggregation from 15s bars

- GIVEN `ohlcv_aggregate(60, ref('ohlcv_15s'), false)`
- WHEN compiled
- THEN valid SQL computes 1m OHLCV bars matching manual window-function calculation

#### Scenario: Daily date_trunc alignment

- GIVEN `ohlcv_aggregate(86400, ref('ohlcv_15s'), true)`
- WHEN compiled
- THEN the bucket alignment clause uses `date_trunc('day', datetime)` not a sliding modulus

### Requirement: Multi-Granularity Models

The system MUST provide 8 incremental dbt models (`ohlcv_{1m|3m|5m|15m|1h|3h|4h|1d}`). Each SHALL call `ohlcv_aggregate()` with its bucket size, SELECT from `ohlcv_15s`, and use `unique_key=(datetime,symbol)`, `materialized='incremental'`.

#### Scenario: Row count proportional to bucket

- GIVEN one day of tick data
- WHEN all 8 models build
- THEN `ohlcv_1d` has ~1/96 the rows of `ohlcv_15s`
- AND coarser granularities have proportionally fewer rows than finer ones

#### Scenario: Monotonic OHLCV across granularities

- GIVEN the same tick window across granularities
- WHEN comparing OHLCV values
- THEN daily high >= hourly high >= 15m high
- AND daily low <= hourly low <= 15m low

### Requirement: Coarse Incremental Build

Coarse models MUST filter incremental loads with `bucket_dt > (SELECT MAX(bucket_dt) FROM this) - INTERVAL (2 * bucket_seconds) SECOND` to handle boundary overlaps.

#### Scenario: Boundary overlap coverage

- GIVEN `ohlcv_1h` last built through `2026-03-15 12:00:00`
- WHEN new 15s data appears near `12:00:00` and the model increments
- THEN the 2h lookback captures boundary-spanning bars
- AND zero rows are lost or double-counted after merge

## MODIFIED Requirements

### Requirement: Bucket Alignment

Buckets MUST align to their timeframe boundaries. Sub-daily: `EXTRACT(SECOND from dt) % bucket_seconds` with second-precision TIMESTAMP. Daily (`is_daily=true`): `date_trunc('day', datetime)` aligning to midnight (00:00:00).
(Previously: 15s-only alignment via 15-second modulus)

#### Scenario: Tick at exact boundary

- GIVEN a tick at `2026-03-15 09:30:00.000`
- WHEN bucketed to any granularity
- THEN it falls into the boundary-starting bucket

#### Scenario: Tick near boundary end

- GIVEN a tick at `09:30:59.999` with 1m granularity
- WHEN bucketed
- THEN it falls into `09:30:00`, next bucket at `09:31:00`

#### Scenario: Daily alignment at calendar midnight

- GIVEN ticks from `2026-03-15 08:00:00` to `2026-03-16 02:00:00`
- WHEN bucketed to 1d with `is_daily=true`
- THEN two buckets: `2026-03-15 00:00:00` and `2026-03-16 00:00:00`
- AND first bucket covers `08:00-24:00` not `08:00-08:00` sliding

### Requirement: API Query by Symbol

`GET /api/v1/ohlcv` MUST accept `symbol` (required), `start_date` (optional), `end_date` (optional), and `granularity` (optional, default=`"15s"`). Invalid granularities SHALL return 422. The endpoint SHALL map `granularity` to table `ohlcv_{granularity}` via validated allow-list. Results sorted by `(datetime, symbol)`.
(Previously: symbol, start_date, end_date only)

#### Scenario: Symbol-only query (backward compat)

- GIVEN bars for `MNQ0626` and `ESU0626`
- WHEN `GET /api/v1/ohlcv?symbol=MNQ0626` (no granularity)
- THEN only `MNQ0626` bars returned, identical to `granularity=15s`

#### Scenario: Filtered by date range

- GIVEN bars spanning multiple days
- WHEN `GET /api/v1/ohlcv?symbol=MNQ0626&start_date=2026-03-15&end_date=2026-03-16`
- THEN bars with `datetime >= 2026-03-15 AND datetime < 2026-03-16`

#### Scenario: Multi-granularity query

- GIVEN 1m and 15s bars for the same symbol
- WHEN `GET /api/v1/ohlcv?symbol=MNQ0626&granularity=1m`
- THEN bars at 1m intervals are returned

#### Scenario: Invalid granularity rejected

- GIVEN `granularity=7s` (not in allow-list)
- WHEN the endpoint is called
- THEN HTTP 422 with a validation error

#### Scenario: Missing symbol

- GIVEN no `symbol` parameter
- WHEN `GET /api/v1/ohlcv?symbol=&granularity=1m`
- THEN HTTP 422

## REMOVED Requirements

None.

## RENAMED Requirements

None.
