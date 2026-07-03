{{ config(materialized='view') }}

SELECT
    SPLIT_PART(REPLACE(REPLACE(filename, '.txt', ''), '/', '\'), '\', -1) AS symbol,
    strptime(SUBSTRING(raw_timestamp, 1, 8) || ' ' || SUBSTRING(raw_timestamp, 10, 6), '%Y%m%d %H%M%S')
        + (CAST(COALESCE(NULLIF(SUBSTRING(raw_timestamp, 17), ''), '0') AS BIGINT) / 10000000.0) * INTERVAL '1 SECOND' AS event_ts,
    bid,
    ask,
    last,
    volume
FROM {{ source('tick_data', 'raw_ticks') }}
