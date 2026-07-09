{{ config(materialized='table') }}

{% set stage_relation = adapter.get_relation(
    database=target.database,
    schema=target.schema,
    identifier='indicator_feature_stage'
) %}

{% if stage_relation is not none %}
select
    datetime,
    symbol,
    timeframe,
    source_model,
    feature_name,
    feature_id,
    parameter_hash,
    parameter_json,
    output_name,
    value,
    computed_at,
    computation_version,
    pandas_ta_classic_version,
    talib_available,
    talib_version,
    talib_used
from {{ stage_relation }}
{% else %}
select
    cast(null as timestamp) as datetime,
    cast(null as varchar) as symbol,
    cast(null as varchar) as timeframe,
    cast(null as varchar) as source_model,
    cast(null as varchar) as feature_name,
    cast(null as varchar) as feature_id,
    cast(null as varchar) as parameter_hash,
    cast(null as varchar) as parameter_json,
    cast(null as varchar) as output_name,
    cast(null as double) as value,
    cast(null as timestamp) as computed_at,
    cast(null as varchar) as computation_version,
    cast(null as varchar) as pandas_ta_classic_version,
    cast(null as boolean) as talib_available,
    cast(null as varchar) as talib_version,
    cast(null as boolean) as talib_used
where false
{% endif %}
