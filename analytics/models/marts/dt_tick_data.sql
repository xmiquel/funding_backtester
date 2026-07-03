{{ config(materialized='table') }}

SELECT
    *,
    ask - bid AS spread,
    (bid + ask) / 2.0 AS mid,
    last >= ask AS is_aggressive_buy,
    last <= bid AS is_aggressive_sell
FROM {{ ref('stg_tick_data') }}
