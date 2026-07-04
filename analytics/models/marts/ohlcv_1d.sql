{{ config(materialized='incremental', unique_key=['datetime', 'symbol']) }}

{{ ohlcv_aggregate(
    bucket_seconds=86400,
    source_ref=ref('ohlcv_15s'),
    is_daily=true,
    lookback_seconds=172800 if is_incremental() else 0,
    this_ref=this if is_incremental() else none
) }}
