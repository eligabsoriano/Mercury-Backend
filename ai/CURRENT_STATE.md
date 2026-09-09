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

### 8. RFM Customer Segmentation (Phase 5 — ✅ Complete)
- Implemented `ml/rfm.py` to query `mart.mart_customer_metrics` via SQLAlchemy and PostgreSQL.
- Quintile scoring on inverted Recency ($R \in [1, 5]$) and Monetary ($M \in [1, 5]$).
- Custom behavioral tiers on Frequency ($F \in [1, 5]$) handling the 96.9% single-order e-commerce skew.
- Segment assignment (Champions, Loyal Customers, Potential Loyalists, New Customers, At Risk, Lost / Inactive, Others).
- Upserted 93,358 rows into `ml.rfm_segments` with composite RFM scores and string labels.
- Validated with **26 out of 26 tests passing** in `tests/test_rfm.py` (14 unit + 12 integration).

### 9. Churn Prediction & Revenue-at-Risk ML (Phase 6 — ✅ Complete)
- Implemented `ml/churn.py` to train and evaluate ML classifiers on 26 customer intelligence features from `mart.mart_customer_metrics` and `ml.rfm_segments`.
- Churn target defined via time-bounded inactivity window (e.g. 90/180 days; default 90 days = 80.09% observed churn).
- Recency target leakage eliminated: `recency_days` and $R$ scores strictly excluded from feature matrix.
- Trained and benchmarked candidate classifiers on stratified test cohort:
  - **HistGradientBoosting**: ROC-AUC: 0.9328 | PR-AUC: 0.9841 | F1: 0.9168 | Precision@10%: 1.0000
  - **Random Forest**: ROC-AUC: 0.9171 | PR-AUC: 0.9805 | F1: 0.9053 | Precision@10%: 1.0000
  - **Logistic Regression**: ROC-AUC: 0.8915 | PR-AUC: 0.9745 | F1: 0.8837 | Precision@10%: 1.0000
- Winning model artifact (HistGradientBoosting pipeline) serialized to `ml/artifacts/churn_model.joblib`.
- Calibrated churn probabilities and Revenue at Risk ($\text{RAR} = P(\text{Churn}) \times \text{lifetime\_spend}$) computed across all 93,358 customers:
  - High Churn Risk ($P \ge 0.70$): 60,274 customers (64.6%) representing R$ 9.55M revenue at risk.
  - Priority 1 (VIP Retention): 23,124 high-spend at-risk customers representing R$ 6.91M revenue at risk.
- Upserted 93,358 rows into `ml.churn_predictions` with indexes on `risk_tier`, `retention_priority`, and `revenue_at_risk DESC`.
- Validated with **28 out of 28 tests passing** in `tests/test_churn.py`.
- Full project test suite: **73 out of 73 tests passing** (0 failures, 0 warnings).

### 10. FastAPI Application Layer (Phase 7 — ✅ Complete)
- Application Architecture:
  - `backend/config.py`: Environment configuration and CORS settings.
  - `backend/database.py`: SQLAlchemy connection pooling with pre-ping, session dependency generator, and live health diagnostics.
  - `backend/schemas/`: Pydantic v2 schemas (`PortfolioOverview`, `SegmentsOverview`, `RevenueAtRiskOverview`, `CustomerDetail`, `CustomerListResponse`, `RFMScorecard`, `ChurnPrediction`, `HealthResponse`).
  - `backend/services/`: High-performance analytical and customer query services (`AnalyticsService`, `CustomerService`).
  - `backend/routers/`: Modular route handlers (`health_router`, `analytics_router`, `customers_router`).
  - `backend/main.py`: Application entrypoint with OpenAPI docs (`/docs`, `/redoc`, `/openapi.json`), CORS middleware, and route registrations.
- Endpoints Implemented & Verified:
  - `GET /health` & `GET /api/health`: Live database latency and service status.
  - `GET /api/analytics/overview`: Macro-level GMV, orders, AOV, repeat rate, portfolio revenue at risk (R$ 12.28M), and VIP retention exposure.
  - `GET /api/analytics/segments`: RFM segment breakdown (counts, percentages, total spend, averages).
  - `GET /api/analytics/rfm`: Alias for RFM segment distribution.
  - `GET /api/analytics/revenue-at-risk`: Financial exposure across risk tiers (High, Medium, Low) and retention priorities, with top at-risk preview.
  - `GET /api/customers`: Paginated customer listings with filtering by RFM segment, churn risk tier, retention priority, state, spend range, ID search, and dynamic sorting.
  - `GET /api/customers/at-risk`: Actionable retention queue sorted by expected revenue at risk descending.
  - `GET /api/customers/{customer_unique_id}`: Comprehensive 360-degree customer intelligence profile with order history, basket diversity, fulfillment friction, review sentiment, RFM scores, and ML churn prediction.
  - `GET /api/customers/{customer_unique_id}/rfm`: Detailed customer RFM scorecard.
  - `GET /api/customers/{customer_unique_id}/churn`: Individual churn probability, risk tier, and retention action.
- Validated with **22 out of 22 tests passing** in `tests/test_api.py`.
- Full project test suite: **94 out of 94 tests passing** across 6 test modules.

### 11. Performance & In-Memory TTL Caching Layer (Phase 2 — ✅ Complete)
- Application Architecture:
  - `backend/cache.py`: High-performance, thread-safe in-memory caching engine protected by `threading.RLock` with monotonic clock-based TTL expiration (`time.monotonic()`) and LRU capacity protection (`max_size=5000`).
  - Automatic filtering of transient and unhashable objects (`Session`, `Request`, `Response`, `bypass_cache`) to guarantee deterministic key generation.
  - Decorator `@cached(ttl=300)` supporting both synchronous and asynchronous functions.
  - First-class support for `?bypass_cache=true` query parameter to force live re-querying and cache refreshment.
  - `backend/database.py`: Tuned connection pooling for serverless PostgreSQL:
    - `pool_size=10`
    - `max_overflow=20`
    - `pool_recycle=300`
    - `pool_timeout=30`
    - `pool_pre_ping=True`
  - Cache Management & Telemetry Endpoints:
    - `GET /api/analytics/cache/stats`: Telemetry on cache hits, misses, bypasses, evictions, active items, and hit ratio percentage.
    - `POST /api/analytics/cache/clear`: Purges active cache entries on demand.
- Validated with **10 out of 10 tests passing** in `tests/test_cache.py`.
- Validated with **22 out of 22 tests passing** in `tests/test_api.py` including caching and bypass verification.
- Full project test suite: **105 out of 105 tests passing** across 7 test suites.

---

## Next Steps
- Implement remaining Phase 1 endpoints: Revenue time-series, cohort retention curves, seller intelligence, product catalog intelligence, and CSV export.
- Implement Phase 3: Production Hardening & API Security (API key/Bearer auth, rate limiting, request tracing).