WITH raw_reviews AS (
    SELECT *
    FROM {{ source('bronze_airbnb', 'raw_reviews') }}
)
SELECT 
    listing_id,
    id AS review_id,
    date,
    reviewer_id,
    reviewer_name,
    comments
FROM raw_reviews
