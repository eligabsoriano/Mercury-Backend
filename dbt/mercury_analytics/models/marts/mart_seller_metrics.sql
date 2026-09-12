-- mart_seller_metrics.sql
-- =============================================================================
-- Mart: Seller Performance Metrics
-- =============================================================================
-- Marketplace seller dimensional attributes pre-aggregated with orders fulfilled,
-- revenue generated, fulfillment delays, late delivery rates, and review feedback.
-- =============================================================================

WITH sellers AS (
    SELECT * FROM {{ ref('stg_sellers') }}
),

order_items AS (
    SELECT * FROM {{ ref('stg_order_items') }}
),

orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),

order_reviews AS (
    SELECT * FROM {{ ref('int_order_reviews_aggregated') }}
),

seller_orders AS (
    SELECT
        oi.seller_id,
        COUNT(DISTINCT oi.order_id)                            AS total_orders_fulfilled,
        COUNT(oi.order_item_id)                                AS total_items_sold,
        COUNT(DISTINCT oi.product_id)                          AS total_unique_products,
        ROUND(COALESCE(SUM(oi.item_revenue), 0.0)::numeric, 2) AS total_revenue,
        ROUND(COALESCE(AVG(oi.item_revenue), 0.0)::numeric, 2) AS avg_item_value,
        ROUND(COALESCE(AVG(o.delivery_delay_days), 0.0)::numeric, 1) AS avg_delivery_delay_days,
        ROUND(COALESCE(AVG(CASE WHEN o.delivery_delay_days > 0 THEN 1.0 ELSE 0.0 END), 0.0)::numeric * 100.0, 2) AS late_delivery_rate,
        ROUND(COALESCE(AVG(r.avg_review_score), 0.0)::numeric, 2) AS avg_review_score,
        ROUND(COALESCE(AVG(CASE WHEN r.avg_review_score >= 4.0 THEN 1.0 ELSE 0.0 END), 0.0)::numeric * 100.0, 2) AS positive_reviews_rate
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    LEFT JOIN order_reviews r ON o.order_id = r.order_id
    GROUP BY oi.seller_id
),

final_mart AS (
    SELECT
        s.seller_id,
        s.city,
        s.state,
        s.zip_prefix,
        COALESCE(so.total_orders_fulfilled, 0)::INTEGER        AS total_orders_fulfilled,
        COALESCE(so.total_items_sold, 0)::INTEGER              AS total_items_sold,
        COALESCE(so.total_unique_products, 0)::INTEGER         AS total_unique_products,
        COALESCE(so.total_revenue, 0.0)::NUMERIC(14,2)         AS total_revenue,
        COALESCE(so.avg_item_value, 0.0)::NUMERIC(10,2)        AS avg_item_value,
        so.avg_delivery_delay_days,
        COALESCE(so.late_delivery_rate, 0.0)::NUMERIC(5,2)     AS late_delivery_rate,
        so.avg_review_score,
        COALESCE(so.positive_reviews_rate, 0.0)::NUMERIC(5,2)  AS positive_reviews_rate
    FROM sellers s
    LEFT JOIN seller_orders so ON s.seller_id = so.seller_id
)

SELECT * FROM final_mart
