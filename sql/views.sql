-- =============================================================================
-- Mercury — Analytical SQL Views
-- =============================================================================
-- These views expose clean, pre-joined datasets for:
--   1. The ML/RFM pipeline (feature engineering)
--   2. Power BI (reporting)
--   3. FastAPI (read-only query layer)
--
-- All views use CREATE OR REPLACE so they are safe to re-run after schema.sql.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- vw_customer_revenue
-- ---------------------------------------------------------------------------
-- Per-customer aggregated revenue, order count, item count, first/last order.
-- This is the primary input for RFM segmentation and ML feature engineering.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_customer_revenue AS
SELECT
    c.customer_id,
    co.country_name,

    -- Recency
    c.first_order_at,
    c.last_order_at,

    -- Frequency
    COUNT(DISTINCT o.invoice)                                  AS order_count,

    -- Monetary
    COALESCE(SUM(oi.revenue), 0)::NUMERIC(14,2)                AS total_revenue,
    COALESCE(AVG(oi.unit_price * oi.quantity / NULLIF(oi.quantity, 0)), 0)::NUMERIC(12,2)
                                                               AS avg_item_value,

    -- Volume
    COALESCE(SUM(oi.quantity), 0)                              AS total_items,
    COUNT(DISTINCT oi.stock_code)                              AS unique_products,

    -- Average order value: total revenue / number of orders
    CASE
        WHEN COUNT(DISTINCT o.invoice) > 0
        THEN (COALESCE(SUM(oi.revenue), 0) / COUNT(DISTINCT o.invoice))::NUMERIC(12,2)
        ELSE 0
    END                                                        AS avg_order_value

FROM customers c
LEFT JOIN countries co ON co.country_id = c.country_id
LEFT JOIN orders    o  ON o.customer_id  = c.customer_id
                       AND o.is_cancelled = FALSE
LEFT JOIN order_items oi ON oi.invoice   = o.invoice
                         AND oi.quantity  > 0   -- exclude return lines
GROUP BY
    c.customer_id,
    c.first_order_at,
    c.last_order_at,
    co.country_name;

COMMENT ON VIEW vw_customer_revenue IS
    'Per-customer revenue aggregates. Primary feed for RFM scoring and ML feature engineering.';


-- ---------------------------------------------------------------------------
-- vw_rfm_base
-- ---------------------------------------------------------------------------
-- Adds recency_days relative to the dataset reference date (max invoice date)
-- so the ML/RFM pipeline can run without knowing the calendar date.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_rfm_base AS
WITH reference_date AS (
    -- Use the latest invoice date across all orders as the analytical snapshot
    SELECT MAX(invoice_date) AS ref_date
    FROM orders
    WHERE is_cancelled = FALSE
)
SELECT
    cr.customer_id,
    cr.country_name,
    cr.first_order_at,
    cr.last_order_at,
    EXTRACT(EPOCH FROM (rd.ref_date - cr.last_order_at)) / 86400
        ::INTEGER                                AS recency_days,
    cr.order_count                               AS frequency,
    cr.total_revenue                             AS monetary,
    cr.avg_order_value,
    cr.unique_products,
    cr.total_items,
    rd.ref_date
FROM vw_customer_revenue cr
CROSS JOIN reference_date rd;

COMMENT ON VIEW vw_rfm_base IS
    'RFM base metrics with recency_days relative to the dataset max invoice date. '
    'Use as input to the Python RFM scoring pipeline.';


-- ---------------------------------------------------------------------------
-- vw_at_risk_customers
-- ---------------------------------------------------------------------------
-- Customers ranked by revenue at risk (monetary × churn_probability).
-- Powers the /customers/at-risk and /customers/revenue-at-risk API endpoints.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_at_risk_customers AS
SELECT
    cm.customer_id,
    co.country_name,
    cm.rfm_segment,
    cm.recency_days,
    cm.frequency,
    cm.monetary,
    cm.churn_probability,
    cm.revenue_at_risk,
    cm.avg_order_value,
    cm.last_order_date,
    cm.updated_at                               AS metrics_updated_at,

    -- Retention priority tier
    CASE
        WHEN cm.churn_probability >= 0.7 AND cm.monetary  >= 1000 THEN 'Critical'
        WHEN cm.churn_probability >= 0.5 AND cm.monetary  >= 500  THEN 'High'
        WHEN cm.churn_probability >= 0.3                           THEN 'Medium'
        ELSE 'Low'
    END                                         AS priority_tier

FROM customer_metrics cm
JOIN customers c  ON c.customer_id  = cm.customer_id
LEFT JOIN countries co ON co.country_id = c.country_id
WHERE cm.churn_probability IS NOT NULL
ORDER BY cm.revenue_at_risk DESC NULLS LAST;

COMMENT ON VIEW vw_at_risk_customers IS
    'Customers ranked by revenue at risk. Feeds the FastAPI /customers/at-risk endpoint '
    'and the Power BI retention dashboard. Priority tier is business-rule defined.';


-- ---------------------------------------------------------------------------
-- vw_segment_summary
-- ---------------------------------------------------------------------------
-- Aggregate counts and revenue totals per RFM segment.
-- Powers the Power BI segment distribution charts.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_segment_summary AS
SELECT
    cm.rfm_segment,
    COUNT(*)                                    AS customer_count,
    SUM(cm.monetary)::NUMERIC(16,2)             AS total_revenue,
    AVG(cm.monetary)::NUMERIC(14,2)             AS avg_revenue,
    AVG(cm.churn_probability)::NUMERIC(6,5)     AS avg_churn_probability,
    SUM(cm.revenue_at_risk)::NUMERIC(16,2)      AS total_revenue_at_risk,
    AVG(cm.recency_days)::NUMERIC(10,1)         AS avg_recency_days,
    AVG(cm.frequency)::NUMERIC(8,2)             AS avg_frequency
FROM customer_metrics cm
WHERE cm.rfm_segment IS NOT NULL
GROUP BY cm.rfm_segment
ORDER BY total_revenue DESC;

COMMENT ON VIEW vw_segment_summary IS
    'Segment-level aggregates for Power BI dashboards and executive summaries.';


-- ---------------------------------------------------------------------------
-- vw_revenue_at_risk_summary
-- ---------------------------------------------------------------------------
-- Single-row summary of total projected revenue exposure.
-- Powers the GET /customers/revenue-at-risk API endpoint.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_revenue_at_risk_summary AS
SELECT
    COUNT(*)                                                         AS total_customers_with_churn_score,
    SUM(CASE WHEN cm.churn_probability >= 0.5 THEN 1 ELSE 0 END)    AS high_risk_customers,
    SUM(cm.revenue_at_risk)::NUMERIC(16,2)                          AS total_revenue_at_risk,
    SUM(CASE WHEN cm.churn_probability >= 0.5
             THEN cm.revenue_at_risk ELSE 0 END)::NUMERIC(16,2)     AS high_risk_revenue_at_risk,
    AVG(cm.churn_probability)::NUMERIC(6,5)                         AS avg_churn_probability,
    MAX(cm.updated_at)                                               AS last_computed_at
FROM customer_metrics cm
WHERE cm.churn_probability IS NOT NULL;

COMMENT ON VIEW vw_revenue_at_risk_summary IS
    'Single-row revenue exposure summary. Feeds GET /customers/revenue-at-risk.';
