-- =============================================================================
-- Mercury — Raw-Level Helper Views
-- =============================================================================
-- These are minimal raw-schema views used by the ingestion layer and for
-- quick data-quality checks.  The full analytics views (customer metrics,
-- RFM base, at-risk customers, segment summaries) are built by dbt as mart
-- models in the mart schema.
--
-- All views use CREATE OR REPLACE — safe to re-run after schema.sql.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- raw.vw_delivered_orders
-- ---------------------------------------------------------------------------
-- Filters to delivered orders only.
-- This is the standard analytical subset for customer metrics:
--   99,441 total orders → 96,478 delivered (97%)
-- Used by dbt staging models and Python ETL validation.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW raw.vw_delivered_orders AS
SELECT
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    o.order_purchase_timestamp,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    -- Delivery delay in days (positive = late, negative = early)
    EXTRACT(EPOCH FROM (
        o.order_delivered_customer_date - o.order_estimated_delivery_date
    )) / 86400.0 AS delivery_delay_days
FROM raw.orders o
JOIN raw.customers c ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered';

COMMENT ON VIEW raw.vw_delivered_orders IS
    'Delivered orders only with customer_unique_id resolved. '
    'Primary analytical subset: 96,478 of 99,441 orders. Feeds dbt staging.';


-- ---------------------------------------------------------------------------
-- raw.vw_order_revenue
-- ---------------------------------------------------------------------------
-- Order-level revenue summary (price + freight per order).
-- Used for ingestion row-count and revenue sanity checks.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW raw.vw_order_revenue AS
SELECT
    i.order_id,
    COUNT(*)                                    AS item_count,
    SUM(i.price)::NUMERIC(14,2)                AS product_revenue,
    SUM(i.freight_value)::NUMERIC(14,2)        AS freight_revenue,
    SUM(i.price + i.freight_value)::NUMERIC(14,2) AS total_revenue
FROM raw.order_items i
GROUP BY i.order_id;

COMMENT ON VIEW raw.vw_order_revenue IS
    'Order-level revenue totals. product_revenue excludes freight; '
    'total_revenue = price + freight. Used for ETL validation.';


-- ---------------------------------------------------------------------------
-- raw.vw_ingestion_summary
-- ---------------------------------------------------------------------------
-- Row count summary across all raw tables.
-- Run after ingestion to confirm expected row counts against source CSV counts.
-- Expected: customers=99441, orders=99441, order_items=112650,
--           order_payments=103886, order_reviews=99224, products=32951,
--           sellers=3095, geolocation=1000163, category_translations=71
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW raw.vw_ingestion_summary AS
SELECT 'raw.customers'             AS table_name, COUNT(*) AS row_count FROM raw.customers
UNION ALL
SELECT 'raw.orders',                               COUNT(*)              FROM raw.orders
UNION ALL
SELECT 'raw.order_items',                          COUNT(*)              FROM raw.order_items
UNION ALL
SELECT 'raw.order_payments',                       COUNT(*)              FROM raw.order_payments
UNION ALL
SELECT 'raw.order_reviews',                        COUNT(*)              FROM raw.order_reviews
UNION ALL
SELECT 'raw.products',                             COUNT(*)              FROM raw.products
UNION ALL
SELECT 'raw.sellers',                              COUNT(*)              FROM raw.sellers
UNION ALL
SELECT 'raw.geolocation',                          COUNT(*)              FROM raw.geolocation
UNION ALL
SELECT 'raw.category_translations',                COUNT(*)              FROM raw.category_translations
UNION ALL
SELECT 'raw_marketing.mql',                        COUNT(*)              FROM raw_marketing.mql
UNION ALL
SELECT 'raw_marketing.closed_deals',               COUNT(*)              FROM raw_marketing.closed_deals
ORDER BY table_name;

COMMENT ON VIEW raw.vw_ingestion_summary IS
    'Row count across all raw tables. Run after CSV ingestion to confirm completeness. '
    'Expected totals from source CSVs are documented in this view''s comment.';
