-- int_order_reviews_aggregated.sql
-- =============================================================================
-- Intermediate: Order Reviews Aggregated
-- =============================================================================
-- Aggregates customer feedback to the order_id level.
-- Handles cases where a single order received multiple reviews.
-- =============================================================================

WITH order_reviews AS (
    SELECT * FROM {{ ref('stg_order_reviews') }}
),

aggregated AS (
    SELECT
        order_id,
        COUNT(*)                                               AS reviews_count,
        ROUND(AVG(review_score), 2)::NUMERIC(3,2)              AS avg_review_score,
        MIN(review_score)                                      AS min_review_score,
        MAX(review_score)                                      AS max_review_score,
        BOOL_OR(is_negative_review)                            AS has_negative_review,
        BOOL_OR(is_positive_review)                            AS has_positive_review,
        MAX(review_created_at)                                 AS latest_review_created_at
    FROM order_reviews
    GROUP BY order_id
)

SELECT * FROM aggregated
