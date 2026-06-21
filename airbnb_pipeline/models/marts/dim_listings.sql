WITH listings AS (
    SELECT * FROM {{ ref('stg_listings') }}
),
reviews AS (
    SELECT * FROM {{ ref('stg_reviews') }}
),
calendar AS (
    SELECT * FROM {{ ref('stg_calendar') }}
),

-- ── Fix 1: Use the snapshot's own date range instead of CURRENT_DATE() ──────
-- The source data is a historical snapshot (Dec 2024). Using CURRENT_DATE()
-- produces a window that falls entirely outside the data, making these columns
-- 100% NULL. We resolve the latest 30 days of available snapshot data instead.
snapshot_max_date AS (
    SELECT MAX(date) AS max_dt FROM calendar
),

review_metrics AS (
    SELECT
        listing_id,
        COUNT(review_id)  AS total_reviews,
        MIN(date)         AS first_review_date,
        MAX(date)         AS last_review_date
    FROM reviews
    GROUP BY listing_id
),
calendar_metrics AS (
    SELECT
        c.listing_id,
        AVG(c.price_usd)                              AS avg_price_next_30_days,
        COUNTIF(c.is_available) / COUNT(c.date)       AS availability_rate_next_30_days
    FROM calendar c
    CROSS JOIN snapshot_max_date s
    WHERE c.date BETWEEN DATE_SUB(s.max_dt, INTERVAL 30 DAY) AND s.max_dt
    GROUP BY c.listing_id
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
    -- Fix 4: COALESCE so listings with no raw price default to 0
    -- rather than propagating NULL through all downstream models.
    COALESCE(l.price_usd, 0) AS current_price,
    l.minimum_nights,
    COALESCE(rm.total_reviews, 0) AS total_reviews,
    rm.first_review_date,
    rm.last_review_date,
    cm.avg_price_next_30_days,
    cm.availability_rate_next_30_days
FROM listings l
LEFT JOIN review_metrics rm ON l.listing_id = rm.listing_id
LEFT JOIN calendar_metrics cm ON l.listing_id = cm.listing_id
