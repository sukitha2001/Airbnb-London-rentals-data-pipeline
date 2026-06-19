WITH listings AS (
    SELECT * FROM {{ ref('stg_listings') }}
)

SELECT
    host_id,
    host_name,
    COUNT(listing_id)                           AS total_listings,
    ARRAY_AGG(DISTINCT neighbourhood)           AS neighbourhoods_hosted_in,
    ARRAY_AGG(DISTINCT room_type)               AS room_types_offered,
    MIN(price_usd)                              AS min_listing_price,
    MAX(price_usd)                              AS max_listing_price,
    ROUND(AVG(price_usd), 2)                    AS avg_listing_price,
    SUM(number_of_reviews)                      AS total_reviews_across_listings
FROM listings
GROUP BY host_id, host_name
