{{ config(materialized='incremental', unique_key=['datetime', 'symbol']) }}

{{ ohlcv_aggregate(
    bucket_seconds=86400,
    source_ref=ref('ohlcv_15s'),
    is_daily=true
) }}

{% if is_incremental() %}
WHERE datetime > (SELECT MAX(datetime) FROM {{ this }}) - INTERVAL '172800' SECOND
{% endif %}
