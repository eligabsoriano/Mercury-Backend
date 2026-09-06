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

---

## Next Phase: Phase 4 — dbt Intermediate & Analytics Marts
- Build `intermediate/int_customer_orders.sql`: Customer-level rollup aggregating order history, dates, and order values by `customer_unique_id`.
- Build `marts/mart_customer_metrics.sql`: Final analytics table calculating RFM metrics (Recency days, Frequency, Monetary spend, AOV), customer delivery friction signals, and review sentiment scores ready for ML churn training and FastAPI serving.