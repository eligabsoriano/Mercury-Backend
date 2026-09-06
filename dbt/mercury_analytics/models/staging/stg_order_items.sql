-- stg_order_items.sql
-- =============================================================================
-- Staging: Order Items
-- =============================================================================
-- Calculates item-level revenue = price + freight_value.
-- Filters to items belonging to delivered orders (via JOIN to stg_orders).
-- =============================================================================

WITH source AS (
    SELECT * FROM {{ source('raw', 'order_items') }}
),

delivered_orders AS (
    SELECT order_id FROM {{ ref('stg_orders') }}
),

cleaned AS (
    SELECT
        oi.order_id,
        oi.order_item_id,
        oi.product_id,
        oi.seller_id,
        oi.shipping_limit_date::TIMESTAMPTZ        AS shipping_limit_at,
        oi.price,
        oi.freight_value,
        (oi.price + oi.freight_value)              AS item_revenue   -- total cost to customer
    FROM source oi
    INNER JOIN delivered_orders d ON d.order_id = oi.order_id
)

SELECT * FROM cleaned
