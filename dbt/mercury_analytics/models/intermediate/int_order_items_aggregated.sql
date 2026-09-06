-- int_order_items_aggregated.sql
-- =============================================================================
-- Intermediate: Order Items Aggregated
-- =============================================================================
-- Aggregates line-item details from stg_order_items to the order_id level.
-- Eliminates Cartesian fan-out when joining orders with payments and reviews.
-- =============================================================================

WITH order_items AS (
    SELECT * FROM {{ ref('stg_order_items') }}
),

aggregated AS (
    SELECT
        order_id,
        COUNT(*)                                               AS item_count,
        SUM(price)::NUMERIC(14,2)                             AS product_revenue,
        SUM(freight_value)::NUMERIC(14,2)                     AS freight_revenue,
        SUM(item_revenue)::NUMERIC(14,2)                      AS total_order_item_revenue,
        COUNT(DISTINCT product_id)                            AS unique_products_count,
        COUNT(DISTINCT seller_id)                             AS unique_sellers_count
    FROM order_items
    GROUP BY order_id
)

SELECT * FROM aggregated
