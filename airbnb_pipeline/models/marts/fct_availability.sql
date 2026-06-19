WITH calendar AS (
    SELECT * FROM {{ ref('stg_calendar') }}
),
listings AS (
    SELECT
        listing_id,
        listing_name,
        host_id,
        host_name,
        neighbourhood,
        room_type
    FROM {{ ref('dim_listings') }}
)

SELECT
    c.listing_id,
    c.date,
    c.is_available,
    c.price_usd,
    c.adjusted_price_usd,
    c.minimum_nights,
    c.maximum_nights,
    -- Enriched from dim_listings
    l.listing_name,
    l.host_id,
    l.host_name,
    l.neighbourhood,
    l.room_type,
    -- Derived fields
    EXTRACT(YEAR FROM c.date)                           AS year,
    EXTRACT(MONTH FROM c.date)                          AS month,
    FORMAT_DATE('%B', c.date)                           AS month_name,
    EXTRACT(DAYOFWEEK FROM c.date)                      AS day_of_week,
    CASE
        WHEN EXTRACT(DAYOFWEEK FROM c.date) IN (1, 7)
        THEN TRUE ELSE FALSE
    END                                                 AS is_weekend
FROM calendar c
LEFT JOIN listings l ON c.listing_id = l.listing_id
