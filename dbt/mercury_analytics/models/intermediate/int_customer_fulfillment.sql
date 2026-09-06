-- int_customer_fulfillment.sql
-- =============================================================================
-- Intermediate: Customer Fulfillment & Delivery Experience
-- =============================================================================
-- Measures fulfillment delays and friction points aggregated by customer_unique_id.
-- Late delivery is a strong operational signal for churn feature engineering.
-- =============================================================================

WITH customers AS (
    SELECT * FROM {{ ref('stg_customers') }}
),

orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),

customer_delivery_base AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        o.delivery_delay_days,
        CASE
            WHEN o.delivery_delay_days > 0 THEN 1
            ELSE 0
        END                                                    AS is_late_order,
        CASE
            WHEN o.delivery_delay_days <= 0 THEN 1
            ELSE 0
        END                                                    AS is_on_time_order
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
),

aggregated AS (
    SELECT
        customer_unique_id,
        ROUND(AVG(delivery_delay_days)::NUMERIC, 2)            AS avg_delivery_delay_days,
        ROUND(MAX(delivery_delay_days)::NUMERIC, 2)            AS max_delivery_delay_days,
        SUM(is_late_order)::INTEGER                            AS late_orders_count,
        SUM(is_on_time_order)::INTEGER                         AS on_time_orders_count,
        ROUND(
            SUM(is_late_order)::NUMERIC / NULLIF(COUNT(*), 0), 4
        )::NUMERIC(6,4)                                        AS late_order_ratio,
        (SUM(is_late_order) > 0)                               AS has_late_delivery
    FROM customer_delivery_base
    GROUP BY customer_unique_id
)

SELECT * FROM aggregated
