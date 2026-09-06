-- dim_customers.sql
-- =============================================================================
-- Mart: Customer Dimension
-- =============================================================================
-- Dimension table for unique customers (customer_unique_id).
-- Surfaces deterministic location, first/last purchase dates, and tenure.
-- =============================================================================

WITH customer_orders AS (
    SELECT * FROM {{ ref('int_customer_orders') }}
),

customer_locations AS (
    SELECT * FROM {{ ref('int_customer_locations') }}
),

dim_customers AS (
    SELECT
        o.customer_unique_id,
        l.primary_city                                         AS city,
        l.primary_state                                        AS state,
        l.primary_zip_prefix                                   AS zip_prefix,
        o.first_purchased_at,
        o.latest_purchased_at,
        o.lifetime_orders,
        (o.lifetime_orders > 1)                                AS is_repeat_buyer,
        DATE_PART(
            'day', o.latest_purchased_at - o.first_purchased_at
        )::INTEGER                                             AS customer_tenure_days
    FROM customer_orders o
    JOIN customer_locations l ON l.customer_unique_id = o.customer_unique_id
)

SELECT * FROM dim_customers
