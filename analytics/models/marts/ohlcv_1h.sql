{{ config(materialized='incremental', unique_key=['datetime', 'symbol']) }}

{{ ohlcv_aggregate(
    bucket_seconds=3600,
    source_ref=ref('ohlcv_15s'),
    lookback_seconds=7200 if is_incremental() else 0,
    this_ref=this if is_incremental() else none
) }}
