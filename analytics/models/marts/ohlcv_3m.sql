{{ config(materialized='incremental', unique_key=['datetime', 'symbol']) }}

{{ ohlcv_aggregate(
    bucket_seconds=180,
    source_ref=ref('ohlcv_15s')
) }}

{% if is_incremental() %}
WHERE datetime > (SELECT MAX(datetime) FROM {{ this }}) - INTERVAL '360' SECOND
{% endif %}
