WITH raw_calendar AS (
    SELECT *
    FROM {{ source('bronze_airbnb', 'raw_calendar') }}
)
SELECT 
    listing_id,
    date,
    available AS is_available,
    CAST(price AS FLOAT64) AS price_usd,
    CAST(
        REPLACE(REPLACE(adjusted_price, '$', ''), ',', '') AS FLOAT64
    ) AS adjusted_price_usd,
    minimum_nights,
    maximum_nights
FROM raw_calendar
