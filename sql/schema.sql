-- =============================================================================
-- Mercury — PostgreSQL Raw Schema (Olist Dataset)
-- =============================================================================
-- Applies to: Neon (PostgreSQL 16) and any standard PostgreSQL ≥ 14
-- Safe to re-run: uses IF NOT EXISTS throughout.
--
-- Schema layout:
--   raw            ← ingested Olist e-commerce CSVs (this file)
--   raw_marketing  ← optional marketing funnel CSVs (separate module)
--   staging        ← dbt staging models (created by dbt at runtime)
--   mart           ← dbt analytics mart models (created by dbt at runtime)
--
-- Key design decision:
--   customer_id in Olist is ORDER-SCOPED (one per order).
--   customer_unique_id is the TRUE returning-customer identifier.
--   RFM, churn, and all customer metrics must be computed on customer_unique_id.
--
-- Column names match the source CSVs exactly (including known dataset typos
--   such as product_name_lenght) to make ingestion validation trivial.
-- =============================================================================


-- ---------------------------------------------------------------------------
-- PostgreSQL schemas
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS raw_marketing;
-- staging and mart schemas are created automatically by dbt


-- ===========================================================================
-- raw.customers
-- ---------------------------------------------------------------------------
-- One row per ORDER in Olist (not per unique customer).
-- customer_id is order-scoped; customer_unique_id is the true customer key.
-- Use customer_unique_id for all RFM and churn analysis.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id              VARCHAR(50)  PRIMARY KEY,
    customer_unique_id       VARCHAR(50)  NOT NULL,
    customer_zip_code_prefix VARCHAR(10),
    customer_city            VARCHAR(100),
    customer_state           VARCHAR(5)
);

COMMENT ON TABLE  raw.customers                      IS 'Olist customers. customer_id is order-scoped; customer_unique_id is the true returning-customer key.';
COMMENT ON COLUMN raw.customers.customer_id          IS 'Order-scoped customer identifier. One row per order, not per unique customer.';
COMMENT ON COLUMN raw.customers.customer_unique_id   IS 'True customer identifier. Use this for all RFM and churn computations.';

CREATE INDEX IF NOT EXISTS idx_raw_customers_unique_id
    ON raw.customers(customer_unique_id);


-- ===========================================================================
-- raw.orders
-- ---------------------------------------------------------------------------
-- One row per order. order_purchase_timestamp is the primary date dimension.
-- Only "delivered" orders are used for customer analytics (96,478 of 99,441).
-- ===========================================================================
CREATE TABLE IF NOT EXISTS raw.orders (
    order_id                      VARCHAR(50)  PRIMARY KEY,
    customer_id                   VARCHAR(50)  NOT NULL
                                               REFERENCES raw.customers(customer_id),
    order_status                  VARCHAR(30),
    order_purchase_timestamp      TIMESTAMPTZ,
    order_approved_at             TIMESTAMPTZ,
    order_delivered_carrier_date  TIMESTAMPTZ,
    order_delivered_customer_date TIMESTAMPTZ,
    order_estimated_delivery_date TIMESTAMPTZ
);

COMMENT ON TABLE  raw.orders                              IS 'Olist orders. Date range: 2016-09 to 2018-10. 96,478 / 99,441 orders have status=delivered.';
COMMENT ON COLUMN raw.orders.order_status                 IS 'delivered | shipped | canceled | unavailable | invoiced | processing | created | approved';
COMMENT ON COLUMN raw.orders.order_purchase_timestamp     IS 'Primary event timestamp — use for recency and time-series analysis.';
COMMENT ON COLUMN raw.orders.order_delivered_customer_date IS 'Actual delivery date. NULL if not yet delivered. Used for delivery-experience features.';

CREATE INDEX IF NOT EXISTS idx_raw_orders_customer
    ON raw.orders(customer_id);

CREATE INDEX IF NOT EXISTS idx_raw_orders_status
    ON raw.orders(order_status);

CREATE INDEX IF NOT EXISTS idx_raw_orders_purchase_ts
    ON raw.orders(order_purchase_timestamp);


-- ===========================================================================
-- raw.order_items
-- ---------------------------------------------------------------------------
-- One row per item per order. Composite PK: (order_id, order_item_id).
-- Revenue per item = price + freight_value.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS raw.order_items (
    order_id            VARCHAR(50)   NOT NULL
                                      REFERENCES raw.orders(order_id),
    order_item_id       INTEGER       NOT NULL,   -- 1-based item sequence within order
    product_id          VARCHAR(50),
    seller_id           VARCHAR(50),
    shipping_limit_date TIMESTAMPTZ,
    price               NUMERIC(12,2) NOT NULL CHECK (price >= 0),
    freight_value       NUMERIC(12,2) NOT NULL CHECK (freight_value >= 0),
    PRIMARY KEY (order_id, order_item_id)
);

COMMENT ON TABLE  raw.order_items              IS 'Line items per order. Revenue = price + freight_value.';
COMMENT ON COLUMN raw.order_items.price        IS 'Product price in BRL (excluding freight).';
COMMENT ON COLUMN raw.order_items.freight_value IS 'Shipping cost in BRL.';

CREATE INDEX IF NOT EXISTS idx_raw_order_items_product
    ON raw.order_items(product_id);

CREATE INDEX IF NOT EXISTS idx_raw_order_items_seller
    ON raw.order_items(seller_id);


-- ===========================================================================
-- raw.order_payments
-- ---------------------------------------------------------------------------
-- One row per payment installment. Composite PK: (order_id, payment_sequential).
-- Orders can have multiple payment methods (e.g., credit card + voucher).
-- ===========================================================================
CREATE TABLE IF NOT EXISTS raw.order_payments (
    order_id              VARCHAR(50)   NOT NULL
                                        REFERENCES raw.orders(order_id),
    payment_sequential    INTEGER       NOT NULL,
    payment_type          VARCHAR(30),   -- credit_card | boleto | voucher | debit_card
    payment_installments  INTEGER,
    payment_value         NUMERIC(12,2),
    PRIMARY KEY (order_id, payment_sequential)
);

COMMENT ON TABLE  raw.order_payments                 IS 'Payment records per order. Multiple rows per order when multiple payment methods are used.';
COMMENT ON COLUMN raw.order_payments.payment_type    IS 'credit_card | boleto | voucher | debit_card | not_defined';
COMMENT ON COLUMN raw.order_payments.payment_value   IS 'Amount paid for this payment record in BRL.';

CREATE INDEX IF NOT EXISTS idx_raw_order_payments_order
    ON raw.order_payments(order_id);

CREATE INDEX IF NOT EXISTS idx_raw_order_payments_type
    ON raw.order_payments(payment_type);


-- ===========================================================================
-- raw.order_reviews
-- ---------------------------------------------------------------------------
-- One row per review. review_id is the PK.
-- review_score (1–5) is used as a customer-experience feature in churn models.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS raw.order_reviews (
    review_id              VARCHAR(50)  NOT NULL,
    order_id               VARCHAR(50)  NOT NULL
                                        REFERENCES raw.orders(order_id),
    review_score           SMALLINT     CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title   TEXT,
    review_comment_message TEXT,
    review_creation_date   TIMESTAMPTZ,
    review_answer_timestamp TIMESTAMPTZ,
    PRIMARY KEY (review_id, order_id)
);

COMMENT ON TABLE  raw.order_reviews             IS 'Customer reviews. review_score (1–5) is a customer satisfaction signal used in churn feature engineering.';
COMMENT ON COLUMN raw.order_reviews.review_score IS '1=worst … 5=best. Distribution: 5→57k, 4→19k, 1→11k, 3→8k, 2→3k.';

CREATE INDEX IF NOT EXISTS idx_raw_order_reviews_order
    ON raw.order_reviews(order_id);

CREATE INDEX IF NOT EXISTS idx_raw_order_reviews_score
    ON raw.order_reviews(review_score);


-- ===========================================================================
-- raw.products
-- ---------------------------------------------------------------------------
-- One row per product. Column names match CSV exactly (including typos).
-- ===========================================================================
CREATE TABLE IF NOT EXISTS raw.products (
    product_id                   VARCHAR(50)  PRIMARY KEY,
    product_category_name        VARCHAR(100),
    product_name_lenght          INTEGER,      -- typo preserved from source CSV
    product_description_lenght   INTEGER,      -- typo preserved from source CSV
    product_photos_qty           INTEGER,
    product_weight_g             INTEGER,
    product_length_cm            INTEGER,
    product_height_cm            INTEGER,
    product_width_cm             INTEGER
);

COMMENT ON TABLE  raw.products                          IS 'Product catalogue. Column typos (lenght) are preserved from the source CSV intentionally.';
COMMENT ON COLUMN raw.products.product_category_name   IS 'Portuguese category name. Join to raw.category_translations for English.';
COMMENT ON COLUMN raw.products.product_name_lenght     IS 'Character count of product name (typo in source: "lenght" = "length").';

CREATE INDEX IF NOT EXISTS idx_raw_products_category
    ON raw.products(product_category_name);


-- ===========================================================================
-- raw.sellers
-- ---------------------------------------------------------------------------
-- One row per seller. 3,095 sellers in the dataset.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS raw.sellers (
    seller_id              VARCHAR(50)  PRIMARY KEY,
    seller_zip_code_prefix VARCHAR(10),
    seller_city            VARCHAR(100),
    seller_state           VARCHAR(5)
);

COMMENT ON TABLE raw.sellers IS 'Seller dimension. 3,095 sellers in the dataset.';


-- ===========================================================================
-- raw.geolocation
-- ---------------------------------------------------------------------------
-- Multiple rows per zip code prefix (lat/lng approximations).
-- No PRIMARY KEY — zip prefix appears many times with slight coord variations.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS raw.geolocation (
    geolocation_zip_code_prefix VARCHAR(10) NOT NULL,
    geolocation_lat             NUMERIC(10,6),
    geolocation_lng             NUMERIC(10,6),
    geolocation_city            VARCHAR(100),
    geolocation_state           VARCHAR(5)
);

COMMENT ON TABLE  raw.geolocation                         IS 'Geolocation reference. 1M rows — many lat/lng per zip. Average to get centroid per zip for mapping.';
COMMENT ON COLUMN raw.geolocation.geolocation_zip_code_prefix IS 'First 5 digits of Brazilian CEP. Not unique — average coordinates per prefix for joins.';

CREATE INDEX IF NOT EXISTS idx_raw_geolocation_zip
    ON raw.geolocation(geolocation_zip_code_prefix);


-- ===========================================================================
-- raw.category_translations
-- ---------------------------------------------------------------------------
-- 71 rows mapping Portuguese product category names to English.
-- ===========================================================================
CREATE TABLE IF NOT EXISTS raw.category_translations (
    product_category_name         VARCHAR(100) PRIMARY KEY,
    product_category_name_english VARCHAR(100)
);

COMMENT ON TABLE raw.category_translations IS '71 PT→EN product category name translations.';


-- ===========================================================================
-- OPTIONAL MODULE — raw_marketing schema
-- ===========================================================================
-- The marketing funnel dataset is SELLER-CENTRIC, not customer-centric.
-- It tracks how Olist acquired sellers, not how customers shop.
-- Included as a separate optional analytical module.
-- ===========================================================================

-- raw_marketing.mql
-- Marketing qualified leads (8,000 rows: organic, paid, social, etc.)
CREATE TABLE IF NOT EXISTS raw_marketing.mql (
    mql_id            VARCHAR(50)  PRIMARY KEY,
    first_contact_date DATE,
    landing_page_id   VARCHAR(100),
    origin            VARCHAR(50)   -- organic_search | paid_search | social | direct_traffic | email | referral | display | other | unknown
);

COMMENT ON TABLE  raw_marketing.mql        IS 'Marketing qualified leads. Seller acquisition funnel — NOT customer-facing.';
COMMENT ON COLUMN raw_marketing.mql.origin IS 'Acquisition channel: organic_search | paid_search | social | direct_traffic | email | referral | display | other | unknown';

-- raw_marketing.closed_deals
-- Leads that converted to active sellers (842 rows)
CREATE TABLE IF NOT EXISTS raw_marketing.closed_deals (
    mql_id                        VARCHAR(50)  PRIMARY KEY
                                               REFERENCES raw_marketing.mql(mql_id),
    seller_id                     VARCHAR(50),
    sdr_id                        VARCHAR(50),
    sr_id                         VARCHAR(50),
    won_date                      DATE,
    business_segment              VARCHAR(100),
    lead_type                     VARCHAR(100),
    lead_behaviour_profile        VARCHAR(100),
    has_company                   BOOLEAN,
    has_gtin                      BOOLEAN,
    average_stock                 VARCHAR(50),
    business_type                 VARCHAR(100),
    declared_product_catalog_size NUMERIC(12,2),
    declared_monthly_revenue      NUMERIC(14,2)
);

COMMENT ON TABLE  raw_marketing.closed_deals IS 'MQLs that converted to active Olist sellers (842 of 8,000 leads). Links to raw.sellers via seller_id.';

CREATE INDEX IF NOT EXISTS idx_raw_mktg_deals_seller
    ON raw_marketing.closed_deals(seller_id);
