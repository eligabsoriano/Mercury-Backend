-- stg_order_reviews.sql
-- =============================================================================
-- Staging: Order Reviews
-- =============================================================================
-- One review per order. review_score (1–5) is used as a customer satisfaction
-- signal in churn feature engineering.
-- Adds a boolean for negative reviews (score ≤ 2).
-- =============================================================================

WITH source AS (
    SELECT * FROM {{ source('raw', 'order_reviews') }}
),

cleaned AS (
    SELECT
        review_id,
        order_id,
        review_score,
        review_score <= 2                              AS is_negative_review,
        review_score >= 4                              AS is_positive_review,
        review_comment_title,
        review_comment_message,
        review_creation_date::TIMESTAMPTZ              AS review_created_at,
        review_answer_timestamp::TIMESTAMPTZ           AS review_answered_at
    FROM source
    WHERE review_score IS NOT NULL
)

SELECT * FROM cleaned
