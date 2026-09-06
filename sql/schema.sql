-- =============================================================================
-- Mercury — PostgreSQL Schema
-- =============================================================================
-- Applies to: Neon (PostgreSQL 16-compatible) and any standard PostgreSQL ≥ 12
-- Safe to re-run: all statements use IF NOT EXISTS.
-- Dependency order: countries → products → customers → orders → order_items
--                   → customer_metrics
--
-- Design notes:
--   - TIMESTAMPTZ stores every timestamp in UTC.
--   - NUMERIC(12,4) for unit prices; NUMERIC(14,2) for aggregated money values.
--   - customer_id uses INTEGER to match the 5-digit CustomerID in Online Retail II.
--   - Generated column `revenue` avoids storing a value that can be derived,
--     while still being indexable and queryable without a join.
--   - customer_metrics is updated by the ML/RFM pipeline after ETL.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- Extension: ensure pgcrypto is available if needed later (safe to skip)
-- ---------------------------------------------------------------------------
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ===========================================================================
-- 1. countries
--    Reference table for country names sourced from the Online Retail II data.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS countries (
    country_id   SERIAL       PRIMARY KEY,
    country_name VARCHAR(100) NOT NULL UNIQUE
);

COMMENT ON TABLE  countries              IS 'Country reference data sourced from Online Retail II.';
COMMENT ON COLUMN countries.country_id   IS 'Surrogate primary key.';
COMMENT ON COLUMN countries.country_name IS 'Full country name as it appears in the raw dataset.';


-- ===========================================================================
-- 2. products
--    Catalogue of distinct products identified by StockCode.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS products (
    stock_code  VARCHAR(20)  PRIMARY KEY,
    description TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  products             IS 'Product catalogue derived from Online Retail II StockCode values.';
COMMENT ON COLUMN products.stock_code  IS 'Natural product identifier from the dataset (e.g. 85123A).';
COMMENT ON COLUMN products.description IS 'Most recent product description; may differ across invoices.';
COMMENT ON COLUMN products.updated_at  IS 'Set by the ETL loader when description changes.';


-- ===========================================================================
-- 3. customers
--    One row per unique CustomerID observed in clean transaction data.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS customers (
    customer_id    INTEGER      PRIMARY KEY,
    country_id     INTEGER      REFERENCES countries(country_id) ON DELETE SET NULL,
    first_order_at TIMESTAMPTZ,
    last_order_at  TIMESTAMPTZ,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  customers               IS 'One row per distinct customer observed in cleaned transaction data.';
COMMENT ON COLUMN customers.customer_id   IS '5-digit CustomerID from the Online Retail II dataset.';
COMMENT ON COLUMN customers.country_id    IS 'Most frequent country for this customer (set by ETL).';
COMMENT ON COLUMN customers.first_order_at IS 'Earliest valid invoice date for this customer.';
COMMENT ON COLUMN customers.last_order_at  IS 'Most recent valid invoice date; used for recency calculation.';

CREATE INDEX IF NOT EXISTS idx_customers_country
    ON customers(country_id);

CREATE INDEX IF NOT EXISTS idx_customers_last_order
    ON customers(last_order_at);


-- ===========================================================================
-- 4. orders
--    Invoice-level transaction header.  One row per unique Invoice number.
--    Cancelled invoices (Invoice starting with 'C') are excluded by ETL.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS orders (
    invoice      VARCHAR(20)  PRIMARY KEY,
    customer_id  INTEGER      NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    country_id   INTEGER      REFERENCES countries(country_id) ON DELETE SET NULL,
    invoice_date TIMESTAMPTZ  NOT NULL,
    is_cancelled BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  orders              IS 'Invoice-level transaction header; one row per Invoice.';
COMMENT ON COLUMN orders.invoice      IS 'Invoice identifier (e.g. 536365). Cancelled invoices begin with C.';
COMMENT ON COLUMN orders.is_cancelled IS 'TRUE if the original invoice begins with C (cancelled order).';
COMMENT ON COLUMN orders.invoice_date IS 'UTC-normalised InvoiceDate from the dataset.';

CREATE INDEX IF NOT EXISTS idx_orders_customer
    ON orders(customer_id);

CREATE INDEX IF NOT EXISTS idx_orders_invoice_date
    ON orders(invoice_date);

CREATE INDEX IF NOT EXISTS idx_orders_customer_date
    ON orders(customer_id, invoice_date);


-- ===========================================================================
-- 5. order_items
--    Line-item detail for each invoice.  One row per (Invoice, StockCode)
--    combination after ETL deduplication.
--    revenue is a generated stored column: quantity * unit_price.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS order_items (
    item_id    BIGSERIAL     PRIMARY KEY,
    invoice    VARCHAR(20)   NOT NULL REFERENCES orders(invoice) ON DELETE CASCADE,
    stock_code VARCHAR(20)   NOT NULL REFERENCES products(stock_code),
    quantity   INTEGER       NOT NULL CHECK (quantity <> 0),
    unit_price NUMERIC(12,4) NOT NULL CHECK (unit_price >= 0),
    revenue    NUMERIC(14,4) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    created_at TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  order_items            IS 'Line-item detail per invoice. Revenue is derived from quantity × unit_price.';
COMMENT ON COLUMN order_items.item_id    IS 'Surrogate key; no natural composite key is reliable in the raw dataset.';
COMMENT ON COLUMN order_items.quantity   IS 'Units sold. ETL excludes zero-quantity rows.';
COMMENT ON COLUMN order_items.unit_price IS 'Price per unit in GBP; zero-price items (gifts/samples) are allowed.';
COMMENT ON COLUMN order_items.revenue    IS 'Generated stored column: quantity × unit_price. Updated automatically on INSERT.';

CREATE INDEX IF NOT EXISTS idx_order_items_invoice
    ON order_items(invoice);

CREATE INDEX IF NOT EXISTS idx_order_items_stock_code
    ON order_items(stock_code);

CREATE INDEX IF NOT EXISTS idx_order_items_invoice_stock
    ON order_items(invoice, stock_code);


-- ===========================================================================
-- 6. customer_metrics
--    One row per customer.  Populated and refreshed by the ML/RFM pipeline.
--    All RFM, churn, and revenue-at-risk values live here.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS customer_metrics (
    customer_id             INTEGER       PRIMARY KEY
                                          REFERENCES customers(customer_id) ON DELETE CASCADE,

    -- ── RFM base metrics ─────────────────────────────────────────────────────
    recency_days            INTEGER,                           -- days since last invoice
    frequency               INTEGER,                           -- distinct invoice count
    monetary                NUMERIC(14,2),                     -- total spend (GBP)

    -- ── RFM scores and segment ───────────────────────────────────────────────
    rfm_r_score             SMALLINT      CHECK (rfm_r_score BETWEEN 1 AND 5),
    rfm_f_score             SMALLINT      CHECK (rfm_f_score BETWEEN 1 AND 5),
    rfm_m_score             SMALLINT      CHECK (rfm_m_score BETWEEN 1 AND 5),
    rfm_segment             VARCHAR(50),   -- e.g. 'VIP', 'At Risk', 'Lost'

    -- ── Churn model output ───────────────────────────────────────────────────
    churn_probability       NUMERIC(6,5)  CHECK (churn_probability BETWEEN 0 AND 1),
    is_churned              BOOLEAN,       -- TRUE if labelled churned in training data

    -- ── Revenue at risk ──────────────────────────────────────────────────────
    revenue_at_risk         NUMERIC(14,2), -- monetary × churn_probability

    -- ── ML feature snapshot (for auditability and API exposure) ──────────────
    avg_order_value         NUMERIC(12,2),
    purchase_frequency      NUMERIC(10,4), -- orders per month or per week
    unique_products         INTEGER,
    return_rate             NUMERIC(6,5)  CHECK (return_rate BETWEEN 0 AND 1),
    avg_days_between_orders NUMERIC(10,2),
    total_items             INTEGER,
    last_order_date         TIMESTAMPTZ,

    -- ── Audit timestamps ─────────────────────────────────────────────────────
    computed_at             TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  customer_metrics                    IS 'Aggregated customer analytics. Refreshed by the RFM and churn ML pipeline.';
COMMENT ON COLUMN customer_metrics.recency_days       IS 'Days between the reference date and the customer''s last invoice.';
COMMENT ON COLUMN customer_metrics.frequency          IS 'Number of distinct valid invoices.';
COMMENT ON COLUMN customer_metrics.monetary           IS 'Sum of all line-item revenue in GBP.';
COMMENT ON COLUMN customer_metrics.rfm_r_score        IS 'Recency quintile score (5 = most recent).';
COMMENT ON COLUMN customer_metrics.rfm_f_score        IS 'Frequency quintile score (5 = highest frequency).';
COMMENT ON COLUMN customer_metrics.rfm_m_score        IS 'Monetary quintile score (5 = highest spend).';
COMMENT ON COLUMN customer_metrics.rfm_segment        IS 'Named segment derived from RFM scores (VIP, Loyal, At Risk, etc.).';
COMMENT ON COLUMN customer_metrics.churn_probability  IS 'Model-predicted probability of churn in [0, 1].';
COMMENT ON COLUMN customer_metrics.is_churned         IS 'Ground-truth churn label used during model training.';
COMMENT ON COLUMN customer_metrics.revenue_at_risk    IS 'monetary × churn_probability: projected revenue loss.';
COMMENT ON COLUMN customer_metrics.return_rate        IS 'Fraction of line items with negative quantity (returns/cancellations).';
COMMENT ON COLUMN customer_metrics.computed_at        IS 'Timestamp when this row was first computed.';
COMMENT ON COLUMN customer_metrics.updated_at         IS 'Timestamp of the most recent pipeline refresh.';

-- Indexes to support FastAPI query patterns and BI dashboard filters
CREATE INDEX IF NOT EXISTS idx_cm_rfm_segment
    ON customer_metrics(rfm_segment);

CREATE INDEX IF NOT EXISTS idx_cm_churn_probability
    ON customer_metrics(churn_probability DESC);

CREATE INDEX IF NOT EXISTS idx_cm_revenue_at_risk
    ON customer_metrics(revenue_at_risk DESC);

CREATE INDEX IF NOT EXISTS idx_cm_is_churned
    ON customer_metrics(is_churned);
