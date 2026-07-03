{{ config(materialized='table') }}

WITH build_anchor AS (
    SELECT 1 AS id FROM {{ ref('dt_tick_data') }} LIMIT 1
)
SELECT DISTINCT
    f.filename,
    CURRENT_TIMESTAMP AS loaded_at
FROM {{ source('tick_data', 'raw_ticks') }} f
CROSS JOIN build_anchor
