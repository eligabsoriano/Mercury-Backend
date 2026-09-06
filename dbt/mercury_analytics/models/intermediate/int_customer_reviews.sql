-- int_customer_reviews.sql
-- =============================================================================
-- Intermediate: Customer Reviews & Satisfaction Signals
-- =============================================================================
-- Aggregates customer review feedback by customer_unique_id.
-- Negative reviews (≤ 2 stars) serve as strong churn predictors.
-- =============================================================================

WITH customers AS (
    SELECT * FROM {{ ref('stg_customers') }}
),

orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),

order_reviews_agg AS (
    SELECT * FROM {{ ref('int_order_reviews_aggregated') }}
),

customer_review_base AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        r.reviews_count,
        r.avg_review_score,
        r.has_negative_review,
        r.has_positive_review
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    JOIN order_reviews_agg r ON r.order_id = o.order_id
),

aggregated AS (
    SELECT
        customer_unique_id,
        SUM(reviews_count)::INTEGER                            AS total_reviews_submitted,
        ROUND(AVG(avg_review_score)::NUMERIC, 2)::NUMERIC(3,2) AS avg_review_score,
        COUNT(*) FILTER (WHERE has_negative_review IS TRUE)    AS negative_reviews_count,
        COUNT(*) FILTER (WHERE has_positive_review IS TRUE)    AS positive_reviews_count,
        BOOL_OR(has_negative_review)                            AS has_negative_review,
        ROUND(
            COUNT(*) FILTER (WHERE has_negative_review IS TRUE)::NUMERIC
            / NULLIF(COUNT(*), 0), 4
        )::NUMERIC(6,4)                                        AS negative_review_ratio
    FROM customer_review_base
    GROUP BY customer_unique_id
)

SELECT * FROM aggregated
