WITH listings AS (
    SELECT * FROM {{ ref('stg_listings') }}
),
reviews AS (
    SELECT * FROM {{ ref('stg_reviews') }}
),
calendar AS (
    SELECT * FROM {{ ref('stg_calendar') }}
),
review_metrics AS (
    SELECT
        listing_id,
        COUNT(review_id) AS total_reviews,
        MIN(date) AS first_review_date,
        MAX(date) AS last_review_date
    FROM reviews
    GROUP BY listing_id
),
calendar_metrics AS (
    SELECT
        listing_id,
        AVG(price_usd) AS avg_price_next_30_days,
        COUNTIF(is_available) / COUNT(date) AS availability_rate_next_30_days
    FROM calendar
    WHERE date BETWEEN CURRENT_DATE() AND DATE_ADD(CURRENT_DATE(), INTERVAL 30 DAY)
    GROUP BY listing_id
)

SELECT
    l.listing_id,
    l.listing_name,
    l.host_id,
    l.host_name,
    l.neighbourhood,
    l.latitude,
    l.longitude,
    l.room_type,
    l.price_usd AS current_price,
    l.minimum_nights,
    COALESCE(rm.total_reviews, 0) AS total_reviews,
    rm.first_review_date,
    rm.last_review_date,
    cm.avg_price_next_30_days,
    cm.availability_rate_next_30_days
FROM listings l
LEFT JOIN review_metrics rm ON l.listing_id = rm.listing_id
LEFT JOIN calendar_metrics cm ON l.listing_id = cm.listing_id
