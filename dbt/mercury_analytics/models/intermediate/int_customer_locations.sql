-- int_customer_locations.sql
-- =============================================================================
-- Intermediate: Customer Primary Locations
-- =============================================================================
-- Determines a single, deterministic primary address per customer_unique_id
-- based on their most recent order timestamp.
-- =============================================================================

WITH customers AS (
    SELECT * FROM {{ ref('stg_customers') }}
),

orders AS (
    SELECT * FROM {{ ref('stg_orders') }}
),

ranked_locations AS (
    SELECT
        c.customer_unique_id,
        c.city,
        c.state,
        c.zip_prefix,
        ROW_NUMBER() OVER (
            PARTITION BY c.customer_unique_id
            ORDER BY o.purchased_at DESC NULLS LAST, c.customer_id
        ) AS location_rank
    FROM customers c
    JOIN orders o ON o.customer_id = c.customer_id
)

SELECT
    customer_unique_id,
    city                                                   AS primary_city,
    state                                                  AS primary_state,
    zip_prefix                                             AS primary_zip_prefix
FROM ranked_locations
WHERE location_rank = 1
