/* Logical uniqueness via (datetime, symbol, timeframe, source_model, feature_id, output_name). */
select
    datetime,
    symbol,
    timeframe,
    source_model,
    feature_id,
    output_name,
    count(*) as row_count
from {{ ref('indicator_features') }}
group by 1, 2, 3, 4, 5, 6
having count(*) > 1
