-- mart_customer_metrics.sql
-- =============================================================================
-- Mart: Customer Intelligence Metrics
-- =============================================================================
-- Primary customer intelligence entity aggregated strictly by customer_unique_id.
-- Unites RFM fundamentals, basket composition, fulfillment friction, and review sentiment.
-- Consumed directly by Phase 5 (RFM segmentation), Phase 6 (Churn ML), and FastAPI.
-- =============================================================================

WITH customer_orders AS (
    SELECT * FROM {{ ref('int_customer_orders') }}
),

customer_locations AS (
    SELECT * FROM {{ ref('int_customer_locations') }}
),

customer_fulfillment AS (
    SELECT * FROM {{ ref('int_customer_fulfillment') }}
),

customer_reviews AS (
    SELECT * FROM {{ ref('int_customer_reviews') }}
),

dataset_benchmark AS (
    SELECT MAX(purchased_at) AS max_dataset_timestamp
    FROM {{ ref('stg_orders') }}
),

final_metrics AS (
    SELECT
        o.customer_unique_id,

        -- Location Profile
        l.primary_city                                         AS city,
        l.primary_state                                        AS state,
        l.primary_zip_prefix                                   AS zip_prefix,

        -- Lifecycle & Recency
        o.first_purchased_at,
        o.latest_purchased_at,
        DATE_PART(
            'day', b.max_dataset_timestamp - o.latest_purchased_at
        )::INTEGER                                             AS recency_days,
        DATE_PART(
            'day', o.latest_purchased_at - o.first_purchased_at
        )::INTEGER                                             AS customer_lifespan_days,

        -- Frequency
        o.lifetime_orders,
        (o.lifetime_orders > 1)                                AS is_repeat_buyer,

        -- Monetary
        o.lifetime_spend,
        o.lifetime_product_spend,
        o.lifetime_freight_spend,
        o.avg_order_value,

        -- Basket Composition
        o.lifetime_items,
        ROUND(
            o.lifetime_items::NUMERIC / NULLIF(o.lifetime_orders, 0), 2
        )::NUMERIC(6,2)                                        AS avg_items_per_order,
        o.total_unique_products_purchased,
        o.total_unique_sellers_contacted,

        -- Fulfillment & Delivery Friction
        COALESCE(f.avg_delivery_delay_days, 0.0)               AS avg_delivery_delay_days,
        COALESCE(f.max_delivery_delay_days, 0.0)               AS max_delivery_delay_days,
        COALESCE(f.late_orders_count, 0)                       AS late_orders_count,
        COALESCE(f.on_time_orders_count, o.lifetime_orders)    AS on_time_orders_count,
        COALESCE(f.late_order_ratio, 0.0)                      AS late_order_ratio,
        COALESCE(f.has_late_delivery, FALSE)                   AS has_late_delivery,

        -- Review Sentiment & Customer Experience
        COALESCE(r.total_reviews_submitted, 0)                 AS total_reviews_submitted,
        r.avg_review_score,
        COALESCE(r.negative_reviews_count, 0)                  AS negative_reviews_count,
        COALESCE(r.positive_reviews_count, 0)                  AS positive_reviews_count,
        COALESCE(r.has_negative_review, FALSE)                 AS has_negative_review,
        COALESCE(r.negative_review_ratio, 0.0)                 AS negative_review_ratio

    FROM customer_orders o
    CROSS JOIN dataset_benchmark b
    JOIN customer_locations l ON l.customer_unique_id = o.customer_unique_id
    LEFT JOIN customer_fulfillment f ON f.customer_unique_id = o.customer_unique_id
    LEFT JOIN customer_reviews r ON r.customer_unique_id = o.customer_unique_id
)

SELECT * FROM final_metrics
