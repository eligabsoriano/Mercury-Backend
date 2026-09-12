-- mart_product_metrics.sql
-- =============================================================================
-- Mart: Product Intelligence Metrics
-- =============================================================================
-- Product catalog dimensional attributes pre-aggregated with sales velocity,
-- gross revenues, average pricing, and review ratings.
-- =============================================================================

WITH products AS (
    SELECT * FROM {{ ref('stg_products') }}
),

order_items AS (
    SELECT * FROM {{ ref('stg_order_items') }}
),

order_reviews AS (
    SELECT * FROM {{ ref('int_order_reviews_aggregated') }}
),

product_sales AS (
    SELECT
        oi.product_id,
        COUNT(oi.order_item_id)                                AS total_units_sold,
        COUNT(DISTINCT oi.order_id)                            AS total_orders_count,
        ROUND(COALESCE(SUM(oi.item_revenue), 0.0)::numeric, 2) AS total_revenue,
        ROUND(COALESCE(AVG(oi.price), 0.0)::numeric, 2)        AS avg_unit_price,
        ROUND(COALESCE(AVG(r.avg_review_score), 0.0)::numeric, 2) AS avg_review_score
    FROM order_items oi
    LEFT JOIN order_reviews r ON oi.order_id = r.order_id
    GROUP BY oi.product_id
),

final_mart AS (
    SELECT
        p.product_id,
        p.category_name_pt,
        p.category_name_en,
        COALESCE(s.total_units_sold, 0)::INTEGER               AS total_units_sold,
        COALESCE(s.total_orders_count, 0)::INTEGER             AS total_orders_count,
        COALESCE(s.total_revenue, 0.0)::NUMERIC(14,2)          AS total_revenue,
        COALESCE(s.avg_unit_price, 0.0)::NUMERIC(10,2)         AS avg_unit_price,
        s.avg_review_score,
        p.product_weight_g,
        p.product_length_cm,
        p.product_height_cm,
        p.product_width_cm,
        p.product_photos_qty
    FROM products p
    LEFT JOIN product_sales s ON p.product_id = s.product_id
)

SELECT * FROM final_mart
