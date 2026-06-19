WITH raw_listings AS (
    SELECT *
    FROM {{ source('bronze_airbnb', 'raw_listings') }}
)
SELECT id AS listing_id,
    name AS listing_name,
    host_id,
    host_name,
    neighbourhood_cleansed AS neighbourhood,
    latitude,
    longitude,
    room_type,
    CAST(price AS FLOAT64) AS price_usd,
    minimum_nights,
    number_of_reviews
FROM raw_listings