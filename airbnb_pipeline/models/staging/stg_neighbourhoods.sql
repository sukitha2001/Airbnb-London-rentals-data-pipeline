WITH raw_neighbourhoods AS (
    SELECT *
    FROM {{ source('bronze_airbnb', 'raw_neighbourhoods') }}
)
SELECT 
    neighbourhood,
    neighbourhood_group,
    ST_GEOGFROMGEOJSON(geometry_json) AS neighbourhood_boundary
FROM raw_neighbourhoods
