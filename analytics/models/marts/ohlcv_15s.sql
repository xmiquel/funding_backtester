{{ config(materialized='incremental', unique_key=['datetime', 'symbol']) }}

WITH bucketed AS (
    SELECT
        date_trunc('second', event_ts)
          - INTERVAL (EXTRACT(SECOND FROM event_ts) % 15) SECOND AS datetime,
        symbol, last, bid, ask, volume,
        ROW_NUMBER() OVER (PARTITION BY symbol, datetime ORDER BY event_ts) AS rn_asc,
        ROW_NUMBER() OVER (PARTITION BY symbol, datetime ORDER BY event_ts DESC) AS rn_desc
    FROM {{ ref('dt_tick_data') }}
    {% if is_incremental() %}
    WHERE datetime > COALESCE((SELECT MAX(datetime) FROM {{ this }}), '2000-01-01')
    {% endif %}
)
SELECT
    datetime, symbol,
    MAX(CASE WHEN rn_asc = 1 THEN last END) AS open,
    MAX(last) AS high,
    MIN(last) AS low,
    MAX(CASE WHEN rn_desc = 1 THEN last END) AS close,
    SUM(volume) AS volume,
    MAX(CASE WHEN rn_asc = 1 THEN bid END) AS bid_open,
    MAX(bid) AS bid_high,
    MIN(bid) AS bid_low,
    MAX(CASE WHEN rn_desc = 1 THEN bid END) AS bid_close,
    MAX(CASE WHEN rn_asc = 1 THEN ask END) AS ask_open,
    MAX(ask) AS ask_high,
    MIN(ask) AS ask_low,
    MAX(CASE WHEN rn_desc = 1 THEN ask END) AS ask_close
FROM bucketed
GROUP BY datetime, symbol
