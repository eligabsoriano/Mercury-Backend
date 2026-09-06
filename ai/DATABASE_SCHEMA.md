# Mercury Database Schema

Last updated: 2026-09-06 (Phase 2 & dbt Staging configured for Olist Dataset)

Database: PostgreSQL (Neon-hosted / local compatible)  
SQL files: `sql/schema.sql` (raw tables + indexes) · `sql/views.sql` (raw helper views)  
Migration runner: `sql/migrate.py`  
Transformation: dbt (`dbt/mercury_analytics/`)

---

## Architecture Principles

1. **Schemas**:
   - `raw`: Direct ingest of the 9 Olist e-commerce CSVs with original column names and types.
   - `raw_marketing`: Ingest of the 2 marketing funnel CSVs (optional seller acquisition module).
   - `staging`: dbt views providing cleaned types, standard casing, and derived staging flags.
   - `intermediate` / `mart`: dbt analytics models resolving entities by `customer_unique_id`.
2. **Customer Key Resolution**:
   - `customer_id` is order-scoped (1 per order).
   - `customer_unique_id` is the true returning customer key.
   - All RFM, churn metrics, and customer aggregations must group by `customer_unique_id`.

---

## 1. `raw` Schema (E-Commerce)

### `raw.customers`
- **Description**: Customer order records.
- **Key**: `customer_id` (VARCHAR(50) PK, order-scoped).
- **Columns**: `customer_unique_id` (VARCHAR(50) NOT NULL, indexed), `customer_zip_code_prefix`, `customer_city`, `customer_state`.
- **Expected Rows**: 99,441.

### `raw.orders`
- **Description**: E-commerce orders and status timestamps.
- **Key**: `order_id` (VARCHAR(50) PK).
- **Columns**: `customer_id` (FK → `raw.customers`), `order_status`, `order_purchase_timestamp` (TIMESTAMPTZ, indexed), `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`, `order_estimated_delivery_date`.
- **Expected Rows**: 99,441 (~96,478 delivered).

### `raw.order_items`
- **Description**: Line items per order.
- **Key**: `(order_id, order_item_id)` PK.
- **Columns**: `order_id` (FK), `order_item_id`, `product_id` (FK → `raw.products`), `seller_id` (FK → `raw.sellers`), `shipping_limit_date`, `price` (NUMERIC(10,2)), `freight_value` (NUMERIC(10,2)).
- **Expected Rows**: 112,650.

### `raw.order_payments`
- **Description**: Payment transactions per order.
- **Key**: `(order_id, payment_sequential)` PK.
- **Columns**: `order_id` (FK), `payment_sequential`, `payment_type` (credit_card, boleto, voucher, debit_card), `payment_installments`, `payment_value` (NUMERIC(10,2)).
- **Expected Rows**: 103,886.

### `raw.order_reviews`
- **Description**: Customer feedback per order.
- **Key**: `review_id` (VARCHAR(50) PK).
- **Columns**: `order_id` (FK), `review_score` (SMALLINT 1–5), `review_comment_title`, `review_comment_message`, `review_creation_date`, `review_answer_timestamp`.
- **Expected Rows**: 99,224.

### `raw.products`
- **Description**: Product catalog dimensions and category.
- **Key**: `product_id` (VARCHAR(50) PK).
- **Columns**: `product_category_name`, `product_name_lenght`, `product_description_lenght`, `product_photos_qty`, `product_weight_g`, `product_length_cm`, `product_height_cm`, `product_width_cm`.
- **Expected Rows**: 32,951.

### `raw.sellers`
- **Description**: Marketplace sellers.
- **Key**: `seller_id` (VARCHAR(50) PK).
- **Columns**: `seller_zip_code_prefix`, `seller_city`, `seller_state`.
- **Expected Rows**: 3,095.

### `raw.geolocation`
- **Description**: Brazilian zip prefix coordinate lookups.
- **Columns**: `geolocation_zip_code_prefix` (indexed), `geolocation_lat`, `geolocation_lng`, `geolocation_city`, `geolocation_state`.
- **Expected Rows**: 1,000,163.

### `raw.category_translations`
- **Description**: English mapping for Portuguese category names.
- **Key**: `product_category_name` (VARCHAR(100) PK).
- **Columns**: `product_category_name_english`.
- **Expected Rows**: 71.

---

## 2. `raw_marketing` Schema (Optional Module)

### `raw_marketing.mql`
- **Key**: `mql_id` (VARCHAR(50) PK).
- **Columns**: `first_contact_date`, `landing_page_id`, `origin`.
- **Expected Rows**: 8,000.

### `raw_marketing.closed_deals`
- **Key**: `mql_id` (VARCHAR(50) PK).
- **Columns**: `seller_id` (VARCHAR(50)), `sdr_id`, `sr_id`, `won_date`, `business_segment`, `lead_type`, `lead_behaviour_profile`, `has_company`, `has_gtin`, `average_stock`, `business_type`, `declared_product_catalog_size`, `declared_monthly_revenue`.
- **Expected Rows**: 842.

---

## 3. Raw Helper Views

- `raw.vw_delivered_orders`: Filters to delivered orders (96,478 rows), joins `customer_unique_id`, and calculates `delivery_delay_days`.
- `raw.vw_order_revenue`: Computes order-level item count, product revenue, freight revenue, and total revenue.
- `raw.vw_ingestion_summary`: Aggregates live row counts across all raw tables to verify ingestion completeness.

---

## 4. dbt Transformation Models (`staging` Schema)

- `stg_customers`: Surfaces `customer_id` and `customer_unique_id`, standardizes city/state casing.
- `stg_orders`: Filters to delivered orders, standardizes timestamp naming, adds `is_delivered` and `delivery_delay_days`.
- `stg_order_items`: Computes item total revenue (`price + freight_value`), joins to delivered orders.
- `stg_order_payments`: Aggregates payments to order level, computes `primary_payment_type`, `has_multiple_payment_methods`.
- `stg_order_reviews`: Flags sentiment (`is_negative_review`, `is_positive_review`), cleans review timestamps.
- `stg_products`: Joins English category translation, renames source typo fields into clean aliases.
- `stg_sellers`: Standardizes city/state casing and conventions.