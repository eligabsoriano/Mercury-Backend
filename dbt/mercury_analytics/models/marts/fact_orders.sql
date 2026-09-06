-- fact_orders.sql
-- =============================================================================
-- Mart: Fact Orders
-- =============================================================================
-- Order-level fact table uniting order lifecycle, payments, revenue, and reviews.
-- Key for Power BI dashboards and granular transactional queries.
-- =============================================================================

WITH orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),

customers AS (
    SELECT * FROM {{ ref('stg_customers') }}
),

order_items AS (
    SELECT * FROM {{ ref('int_order_items_aggregated') }}
),

order_payments AS (
    SELECT * FROM {{ ref('stg_order_payments') }}
),

order_reviews AS (
    SELECT * FROM {{ ref('int_order_reviews_aggregated') }}
),

fact_orders AS (
    SELECT
        o.order_id,
        o.customer_id,                                         -- order-scoped identifier
        c.customer_unique_id,                                  -- true customer dimension key
        o.order_status,
        o.purchased_at,
        o.approved_at,
        o.shipped_at,
        o.delivered_at,
        o.estimated_delivery_at,
        o.delivery_delay_days,
        (o.delivery_delay_days > 0)                            AS is_late_delivery,

        -- Revenue & Items
        COALESCE(i.item_count, 0)                              AS item_count,
        COALESCE(i.unique_products_count, 0)                   AS unique_products_count,
        COALESCE(i.unique_sellers_count, 0)                    AS unique_sellers_count,
        COALESCE(i.product_revenue, 0.0)                       AS product_revenue,
        COALESCE(i.freight_revenue, 0.0)                       AS freight_revenue,
        COALESCE(i.total_order_item_revenue, 0.0)              AS total_revenue,

        -- Payment Details
        p.total_payment_value,
        p.primary_payment_type,
        p.total_installments,
        COALESCE(p.has_multiple_payment_methods, FALSE)        AS has_multiple_payment_methods,

        -- Review Feedback
        COALESCE(r.reviews_count, 0)                           AS reviews_count,
        r.avg_review_score,
        COALESCE(r.has_negative_review, FALSE)                 AS has_negative_review,
        COALESCE(r.has_positive_review, FALSE)                 AS has_positive_review

    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    LEFT JOIN order_items i ON i.order_id = o.order_id
    LEFT JOIN order_payments p ON p.order_id = o.order_id
    LEFT JOIN order_reviews r ON r.order_id = o.order_id
)

SELECT * FROM fact_orders
