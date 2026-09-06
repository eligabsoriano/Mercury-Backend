-- stg_orders.sql
-- =============================================================================
-- Staging: Orders
-- =============================================================================
-- Filters to delivered orders only — the standard analytical subset.
-- Renames timestamp columns to shorter, cleaner names.
-- Adds a boolean is_delivered flag and a delivery_delay_days derived column.
--
-- Delivered orders: 96,478 of 99,441 (97%)
-- Date range: 2016-09-04 → 2018-10-17
-- =============================================================================

WITH source AS (
    SELECT * FROM {{ source('raw', 'orders') }}
),

cleaned AS (
    SELECT
        order_id,
        customer_id,                                       -- order-scoped FK to stg_customers
        order_status,
        order_purchase_timestamp::TIMESTAMPTZ              AS purchased_at,
        order_approved_at::TIMESTAMPTZ                     AS approved_at,
        order_delivered_carrier_date::TIMESTAMPTZ          AS shipped_at,
        order_delivered_customer_date::TIMESTAMPTZ         AS delivered_at,
        order_estimated_delivery_date::TIMESTAMPTZ         AS estimated_delivery_at,

        order_status = 'delivered'                         AS is_delivered,

        -- Delivery delay: positive = late, negative = early, NULL if not delivered
        CASE
            WHEN order_delivered_customer_date IS NOT NULL
             AND order_estimated_delivery_date IS NOT NULL
            THEN EXTRACT(EPOCH FROM (
                    order_delivered_customer_date::TIMESTAMPTZ
                    - order_estimated_delivery_date::TIMESTAMPTZ
                )) / 86400.0
        END                                                AS delivery_delay_days

    FROM source
    WHERE order_status = 'delivered'   -- analytical subset: exclude non-delivered
)

SELECT * FROM cleaned
