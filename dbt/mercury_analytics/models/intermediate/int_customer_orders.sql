-- int_customer_orders.sql
-- =============================================================================
-- Intermediate: Customer Order History
-- =============================================================================
-- Aggregates delivered order activity by customer_unique_id.
-- Resolves customer_id (order-scoped) to customer_unique_id (true customer).
-- =============================================================================

WITH customers AS (
    SELECT * FROM {{ ref('stg_customers') }}
),

orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),

order_items_agg AS (
    SELECT * FROM {{ ref('int_order_items_aggregated') }}
),

customer_order_base AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        o.purchased_at,
        COALESCE(i.item_count, 0)                 AS item_count,
        COALESCE(i.product_revenue, 0.0)          AS product_revenue,
        COALESCE(i.freight_revenue, 0.0)          AS freight_revenue,
        COALESCE(i.total_order_item_revenue, 0.0) AS total_order_revenue,
        COALESCE(i.unique_products_count, 0)      AS unique_products_count,
        COALESCE(i.unique_sellers_count, 0)       AS unique_sellers_count
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    LEFT JOIN order_items_agg i ON i.order_id = o.order_id
),

customer_rollups AS (
    SELECT
        customer_unique_id,
        MIN(purchased_at)                                      AS first_purchased_at,
        MAX(purchased_at)                                      AS latest_purchased_at,
        COUNT(DISTINCT order_id)                               AS lifetime_orders,
        SUM(item_count)::INTEGER                               AS lifetime_items,
        SUM(product_revenue)::NUMERIC(14,2)                    AS lifetime_product_spend,
        SUM(freight_revenue)::NUMERIC(14,2)                    AS lifetime_freight_spend,
        SUM(total_order_revenue)::NUMERIC(14,2)                AS lifetime_spend,
        ROUND(
            SUM(total_order_revenue) / NULLIF(COUNT(DISTINCT order_id), 0), 2
        )::NUMERIC(12,2)                                       AS avg_order_value,
        SUM(unique_products_count)::INTEGER                    AS total_unique_products_purchased,
        SUM(unique_sellers_count)::INTEGER                     AS total_unique_sellers_contacted
    FROM customer_order_base
    GROUP BY customer_unique_id
)

SELECT * FROM customer_rollups
