{% macro ohlcv_aggregate(bucket_seconds, source_ref, is_daily=false) %}

{% if is_daily %}
{% set bucket_expr -%}
    date_trunc('day', datetime)
{%- endset %}
{% else %}
{% set bucket_expr -%}
    CAST(TIMESTAMP 'epoch' + CAST(FLOOR(EXTRACT(epoch FROM datetime) / {{ bucket_seconds }}) * {{ bucket_seconds }} AS BIGINT) * INTERVAL '1 second' AS TIMESTAMP)
{%- endset %}
{% endif %}

WITH bucketed AS (
    SELECT
        {{ bucket_expr }} AS bucket_dt,
        symbol, open, high, low, close, volume,
        bid_open, bid_high, bid_low, bid_close,
        ask_open, ask_high, ask_low, ask_close,
        datetime AS src_dt,
        ROW_NUMBER() OVER (
            PARTITION BY symbol, {{ bucket_expr }}
            ORDER BY datetime
        ) AS rn_asc,
        ROW_NUMBER() OVER (
            PARTITION BY symbol, {{ bucket_expr }}
            ORDER BY datetime DESC
        ) AS rn_desc
    FROM {{ source_ref }}
)
SELECT
    bucket_dt AS datetime,
    symbol,
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
GROUP BY bucket_dt, symbol

{% endmacro %}
