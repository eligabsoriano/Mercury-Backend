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
- Validated with **25 out of 25 tests passing** in `tests/test_api.py`.
- Validated with **6 out of 6 tests passing** in `tests/test_sellers.py`.
- Validated with **6 out of 6 tests passing** in `tests/test_products.py`.
- Full project test suite: **120 out of 120 tests passing** across 9 test suites.

### 12. Domain & Analytical Endpoints (Phase 1 — ✅ Complete)
- Application Architecture:
  - `backend/schemas/analytics.py`: Added `RevenueTrendPoint`, `RevenueAnalyticsResponse`, `CohortRetentionPoint`, and `RetentionAnalyticsResponse`.
  - `backend/schemas/seller.py`: New schemas `SellerSummary`, `SellerDetail`, and `SellerListResponse`.
  - `backend/schemas/product.py`: New schemas `ProductSummary`, `CategorySummary`, `ProductListResponse`, and `CategoryListResponse`.
  - `backend/services/analytics_service.py`: Added `get_revenue_trends` and `get_cohort_retention` (both cached with TTL 300s).
  - `backend/services/seller_service.py`: New `SellerService` with paginated seller listings, state filters, sort orders, and seller 360 profiles with top categories.
  - `backend/services/product_service.py`: New `ProductService` with paginated catalog search, category aggregation, and product 360 scorecards.
  - `backend/services/customer_service.py`: Added `stream_customers_csv` generator for high-efficiency campaign export streaming.
  - `backend/routers/analytics.py`: Added `GET /api/analytics/revenue` and `GET /api/analytics/retention`.
  - `backend/routers/sellers.py`: New `sellers_router` with `GET /api/sellers` and `GET /api/sellers/{id}`.
  - `backend/routers/products.py`: New `products_router` with `GET /api/products`, `GET /api/products/categories`, and `GET /api/products/{id}`.
  - `backend/routers/customers.py`: Added `GET /api/customers/export` streaming CSV endpoint.
  - `backend/main.py`: Registered all routers and updated OpenAPI metadata and root navigation map.
- Validated with **25 out of 25 tests passing** in `tests/test_api.py`.
- Validated with **6 out of 6 tests passing** in `tests/test_sellers.py`.
- Validated with **6 out of 6 tests passing** in `tests/test_products.py`.
- Full project test suite: **120 out of 120 tests passing** across 9 test suites.

### 13. Production Hardening & API Security (Phase 3 — ✅ Complete)
- Application Architecture:
  - `backend/config.py`: Added runtime configurations for `REQUIRE_AUTH`, `API_KEYS`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `RATE_LIMIT_ENABLED`, and `RATE_LIMIT_REQUESTS_PER_MINUTE`.
  - `backend/security.py`: Dual-scheme authentication engine:
    - `X-API-Key` header authentication matching configurable pre-shared keys with constant-time equality comparisons.
    - Bearer JWT authentication with standard base64url HMAC-SHA256 signing and verification (`create_access_token`, `decode_access_token`).
    - FastAPI dependency `verify_auth` enforcing authentication when `REQUIRE_AUTH=true` while exempting public endpoints (`/`, `/health`, `/api/health`, `/docs`, `/redoc`, `/openapi.json`, `/api/auth/token`). In local dev/test (`REQUIRE_AUTH=false`), passes through as an authenticated developer context.
    - Identity introspection dependency `get_current_user`.
  - `backend/rate_limit.py`: In-memory sliding-window rate limiter utilizing high-resolution monotonic timestamps (`time.monotonic()`) and `threading.RLock`. Respects `X-Forwarded-For` and `X-Real-IP` proxies.
  - `backend/middleware.py`: ASGI middleware `RequestTracingAndSecurityMiddleware`:
    - Generates or preserves incoming `X-Request-ID` across all requests and responses.
    - Calculates execution latency via `time.perf_counter()` and attaches `X-Process-Time` (e.g. `12.34ms`).
    - Enforces rate limiting on non-exempt routes, returning HTTP 429 Too Many Requests with `Retry-After` header.
    - Emits structured access logs under `mercury.access`.
    - Intercepts unhandled exceptions to return HTTP 500 while preserving the unique `X-Request-ID` trace.
  - `backend/schemas/auth.py` & `backend/routers/auth.py`: Token generation route `POST /api/auth/token` and caller profile route `GET /api/auth/me`.
- Validated with **18 out of 18 tests passing** in `tests/test_security.py`.
- Full project test suite: **138 out of 138 tests passing** across 10 test suites.

### 14. Containerization & Cloud Deployment (Phase 4 — ✅ Complete)
- Application Architecture:
  - `Dockerfile`: Production multi-stage Dockerfile built on `python:3.13-slim`. Isolates build tools to the builder stage, runs as unprivileged user `mercury` (UID 1000), includes automatic container healthcheck pointing to `/health`.
  - `.dockerignore`: Comprehensive exclusion list omitting git metadata, local virtualenvs, secret `.env` files, raw datasets, dbt artifacts, and compiler caches.
  - `docker-compose.yml`: Local multi-container development and staging configuration with `8000:8000` port forwarding, `.env` binding, hot-reload volume mounts, and service health checks.
  - `Procfile`: Cloud PaaS process descriptor for Heroku, Railway, and Render (`web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT`).
  - `render.yaml`: Infrastructure-as-code blueprint for automated, zero-downtime deployment on Render with health checks and environment variable schemas.
  - `docs/deployment.md`: Operational guide detailing Docker commands, compose workflows, and cloud hosting checklists.
- Validated with **5 out of 5 tests passing** in `tests/test_deployment.py`.
- Full project test suite: **143 out of 143 tests passing** across 11 test suites.

### 15. Automated CI/CD Pipeline (Phase 5 — ✅ Complete)
- Application Architecture:
  - `.github/workflows/ci.yml`: Automated GitHub Actions pipeline triggered on push to `main` and all Pull Requests targeting `main`.
  - Quality Gates:
    1. Python 3.13 setup with pip dependency caching.
    2. Linting: `ruff check backend/ ml/ tests/`.
    3. Formatting: `ruff format --check backend/ ml/ tests/`.
    4. Test execution: `pytest tests/ -v`.
  - `pyproject.toml`: Modern project tooling configuration defining ruff lint rules, format settings, line lengths, and test path resolution.
  - `requirements.txt`: Pinned `ruff==0.16.6` and `pyyaml==6.0.2`.
- Validated with **3 out of 3 tests passing** in `tests/test_ci.py`.
- Full project test suite: **146 out of 146 tests passing** across 12 test suites.

### 16. Client Integration & Schema Contracts (Phase 6 — ✅ Complete)
- Application Architecture:
  - `scripts/export_openapi.py`: CLI and programmatic script generating static `openapi.json` from the FastAPI application without booting a live server.
  - `openapi.json`: Static OpenAPI 3.1 specification declaring all 25 live endpoints and 32 Pydantic schemas.
  - `types/api.ts`: 2,502 lines of TypeScript type definitions generated via `openapi-typescript` for React and Flutter client consumption.
  - `package.json`: NPM package metadata with automated code generation commands (`npm run codegen`, `npm run export:openapi`, `npm run generate:types`).
  - `docs/powerbi_setup.md`: Complete Microsoft Power BI operational guide covering DirectQuery connection parameters, star-schema dimensional relationships (`dim_customers`, `fact_orders`, `mart_customer_metrics`, `rfm_segments`, `churn_predictions`), production DAX metric formulas, and visual recommendations.
- Validated with **6 out of 6 tests passing** in `tests/test_client_contracts.py`.
- Full project test suite: **152 out of 152 tests passing** across 13 test suites (when connected to live Neon PostgreSQL).

### 17. Backend Audit & Hardening Phase (Snapshot date: 2026-09-12 — ✅ Complete)
- Conducted comprehensive backend codebase audit against documentation, API contracts, database, tests, and CI/CD pipelines.
- Implemented **Phase 7: Test Suite Isolation, CI Hardening & Mart Optimization**:
  - `tests/conftest.py`: Session-level autouse database mock fixture enabling 100% isolated test suite runs offline and in GitHub Actions CI (114 passing, 38 skipped, 0 failures).
  - `tests/fixtures/sample_data/`: 11 synthetic schema-aligned CSV sample datasets unblocking `tests/test_etl_ingestion.py`.
  - `tests/test_security.py`: Isolated rate limiting test to cache endpoint, guaranteeing deterministic HTTP 429 validation.
  - `backend/config.py`: Harmonized `ENV` and `APP_ENV` environment variable resolution.
  - `dbt/mercury_analytics/models/marts/`: Created materialized dbt marts `mart_product_metrics` and `mart_seller_metrics`, refactoring `ProductService` and `SellerService` to query them directly.
  - Codebase cleanup: Removed dead boilerplate (`Base = declarative_base()` and `PaginatedResponse[T]`) and documented `GET /api/customers/segments`.

---

## Roadmap Completion Status
- **Phases 1–6 (Functional Baseline & Integrations)**: ✅ 100% Complete & Verified
- **Phase 7 (Test Isolation, CI Hardening & Mart Optimization)**: ✅ 100% Complete & Verified
  - [x] 7.1 Test Suite Isolation & Database Mocking (`tests/test_api.py`, `tests/test_products.py`, `tests/test_sellers.py`)
  - [x] 7.2 Synthetic Ingestion Test Fixtures (`tests/test_etl_ingestion.py`)
  - [x] 7.3 Rate Limiting Test Isolation (`tests/test_security.py`)
  - [x] 7.4 Environment Configuration Harmonization (`APP_ENV` vs `ENV`)
  - [x] 7.5 Materialized Analytical Marts for Products & Sellers (`mart.mart_product_metrics`, `mart.mart_seller_metrics`)
  - [x] 7.6 Codebase Hygiene & Endpoint Harmonization (`GET /api/customers/segments`)