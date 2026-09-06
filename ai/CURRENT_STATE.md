# Mercury Current State

Snapshot date: 2026-09-06.

---

## What Has Been Completed

### 1. Requirements & Scaffolding
- Added `dbt-postgres` to `requirements.txt` and installed into `.venv`.
- Configured `.gitignore` to protect datasets (`Brazilian E-Commerce-Public-Dataset-by-Olist`, `Marketing-Funnel-by-Olist`, `data/`), local credentials, and dbt build outputs (`target/`, `logs/`, `profiles.yml`).
- Initialized core folder structures (`backend/`, `data/`, `dbt/`, `etl/`, `ml/`, `sql/`, `tests/`, `notebooks/`).

### 2. PostgreSQL Schema & Migration (Olist Dataset)
- `sql/schema.sql`: DDL for 9 raw e-commerce tables + 2 raw marketing tables with appropriate column types, keys, and indexes.
- `sql/views.sql`: Raw helper views (`raw.vw_delivered_orders`, `raw.vw_order_revenue`, `raw.vw_ingestion_summary`).
- `sql/migrate.py`: Fully transactional migration runner that cleans old legacy tables, creates `raw` and `raw_marketing` schemas, and verifies schema object presence.
- **Verified on Neon Database**: Migration successfully executed. All 11 tables and 3 views exist on the live Neon PostgreSQL instance.

### 3. dbt Scaffolding (`dbt/mercury_analytics`)
- Created dbt project configured for PostgreSQL (`staging` and `mart` schemas).
- Configured `sources.yml` covering all raw tables and data types.
- Implemented 7 staging models:
  - `stg_customers`: Resolves `customer_id` and `customer_unique_id`.
  - `stg_orders`: Filters delivered orders and derives `delivery_delay_days`.
  - `stg_order_items`: Computes line-item total revenue (`price + freight_value`).
  - `stg_order_payments`: Aggregates order-level payment structures.
  - `stg_order_reviews`: Flags positive/negative review sentiment.
  - `stg_products`: Enriches with English category translations and clean dimensions.
  - `stg_sellers`: Standardizes city and state names.
- Configured `schema.yml` with documentation and 54 generic tests.
- **Verified**: `dbt debug` and `dbt parse` completed successfully with live database connection.

### 4. Raw Data Ingestion (ETL) & Verification (✅ Complete)
- Implemented `etl/ingest.py` using PostgreSQL `COPY` streaming with dependency-ordered loading and automatic schema truncation.
- Loaded all 11 tables (1,559,723 rows total) across `raw.*` and `raw_marketing.*` into Neon.
- Verified live counts via `raw.vw_ingestion_summary`.

### 5. dbt Staging Materialization & Testing (✅ Complete)
- Created `generate_schema_name.sql` macro to materialize staging models directly in `staging.*`.
- Materialized 7 staging views in `staging.*` (`dbt run --select staging`).
- Executed full test suite (`dbt test --select staging`): **53 out of 53 tests passed** (0 errors, 0 warnings).

### 6. Project Documentation (✅ Complete)
- Updated `README.md` from `up.md`.
- Rewrote `docs/architecture.md` and `docs/methodology.md` for Olist.
- Synchronized all `ai/` context files.

### 7. dbt Intermediate & Analytics Marts (Phase 4 — ✅ Complete)
- Built order-level aggregations (`int_order_items_aggregated`, `int_order_reviews_aggregated`) to eliminate multi-item Cartesian fan-out.
- Built customer-level rollups (`int_customer_locations`, `int_customer_orders`, `int_customer_fulfillment`, `int_customer_reviews`) strictly on `customer_unique_id`.
- Materialized 3 mart tables in `mart.*`:
  - `mart.dim_customers`: 93,358 rows (unique delivered customers, deterministic location, tenure).
  - `mart.fact_orders`: 96,478 rows (delivered orders with payments, items, reviews, delivery delays).
  - `mart.mart_customer_metrics`: 93,358 rows (central Customer Intelligence table with RFM base, `recency_days`, AOV, delivery friction, and review sentiment).
- Validated with **95 out of 95 dbt tests passing** (`PASS=95 WARN=0 ERROR=0`).
- Validated with **19 out of 19 pytest tests passing** (`tests/test_dbt_models.py`, `tests/test_database_schema.py`, `tests/test_etl_ingestion.py`).

---

## Next Phase: Phase 5 — RFM Customer Segmentation (Analytics Layer)
- Implement `ml/rfm.py` to query `mart.mart_customer_metrics`.
- Score Recency ($R$) and Monetary ($M$) quintiles (1–5).
- Apply tailored e-commerce Frequency ($F$) logic ($F=1$ vs $F \ge 2$).
- Assign customer segments: Champions, Loyal Customers, Potential Loyalists, At Risk, Lost, New Customers.
- Materialize or persist RFM segment labels back to PostgreSQL for ML churn modeling and API serving.