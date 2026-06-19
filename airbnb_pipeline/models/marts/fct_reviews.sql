WITH reviews AS (
    SELECT * FROM {{ ref('stg_reviews') }}
),
listings AS (
    SELECT * FROM {{ ref('dim_listings') }}
)

SELECT
    r.review_id,
    r.listing_id,
    r.date AS review_date,
    r.reviewer_id,
    r.reviewer_name,
    r.comments,
    l.listing_name,
    l.neighbourhood,
    l.room_type,
    l.host_id,
    l.host_name
FROM reviews r
LEFT JOIN listings l ON r.listing_id = l.listing_id
