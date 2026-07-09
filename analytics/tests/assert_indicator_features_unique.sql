/* Logical uniqueness via (datetime, symbol, timeframe, source_model, feature_id, output_name).
   Includes computed_at to also assert deterministic reproducibility:
   same logical key must produce identical computed_at values on rerun. */
select
    datetime,
    symbol,
    timeframe,
    source_model,
    feature_id,
    output_name,
    computed_at,
    count(*) as row_count
from {{ ref('indicator_features') }}
group by 1, 2, 3, 4, 5, 6, 7
having count(*) > 1
