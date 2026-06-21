WITH neighbourhoods AS (
    SELECT * FROM {{ ref('stg_neighbourhoods') }}
),
listings AS (
    SELECT * FROM {{ ref('stg_listings') }}
),
listing_stats AS (
    SELECT
        neighbourhood,
        COUNT(listing_id)           AS total_listings,
        COUNT(DISTINCT host_id)     AS total_hosts,
        ROUND(AVG(price_usd), 2)    AS avg_price_usd,
        MIN(price_usd)              AS min_price_usd,
        MAX(price_usd)              AS max_price_usd
    FROM listings
    GROUP BY neighbourhood
)

SELECT
    n.neighbourhood,
    -- Fix 2: Inside Airbnb's London GeoJSON does not populate neighbourhood_group
    -- for any of the 33 London boroughs — this field is always NULL in the source.
    -- We default it to 'London' so the column is usable in downstream queries.
    COALESCE(n.neighbourhood_group, 'London') AS neighbourhood_group,
    n.neighbourhood_boundary,
    COALESCE(ls.total_listings, 0)  AS total_listings,
    COALESCE(ls.total_hosts, 0)     AS total_hosts,
    ls.avg_price_usd,
    ls.min_price_usd,
    ls.max_price_usd
FROM neighbourhoods n
LEFT JOIN listing_stats ls ON n.neighbourhood = ls.neighbourhood
