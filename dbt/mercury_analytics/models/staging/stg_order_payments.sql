-- stg_order_payments.sql
-- =============================================================================
-- Staging: Order Payments
-- =============================================================================
-- Aggregates payments to the order level (total paid, primary payment type).
-- Multiple payment methods per order are collapsed into a single summary row.
-- =============================================================================

WITH source AS (
    SELECT * FROM {{ source('raw', 'order_payments') }}
),

-- Total payment value per order across all payment types
order_totals AS (
    SELECT
        order_id,
        SUM(payment_value)          AS total_payment_value,
        SUM(payment_installments)   AS total_installments,
        COUNT(DISTINCT payment_type) AS payment_method_count
    FROM source
    GROUP BY order_id
),

-- Primary payment type = the one with the highest payment_value
primary_payment AS (
    SELECT DISTINCT ON (order_id)
        order_id,
        payment_type                AS primary_payment_type
    FROM source
    ORDER BY order_id, payment_value DESC
),

joined AS (
    SELECT
        ot.order_id,
        pp.primary_payment_type,
        ot.total_payment_value,
        ot.total_installments,
        ot.payment_method_count,
        ot.payment_method_count > 1 AS has_multiple_payment_methods
    FROM order_totals ot
    LEFT JOIN primary_payment pp ON pp.order_id = ot.order_id
)

SELECT * FROM joined
