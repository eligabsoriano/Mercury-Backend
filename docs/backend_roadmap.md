# Mercury Backend Engineering Roadmap & Implementation Specification

This document defines the roadmap and engineering plan to advance the **Mercury Customer Intelligence & Retention Analytics Backend** from its current functional baseline (~80% completion) to full production maturity (100% completion).

---

## 1. Executive Summary & Baseline

### Current Completion Status: ~92% (Backend) / ~75% (Full Project)
- **Data & Migration Layer**: 11 raw tables, 3 views, 1.56M records in Neon PostgreSQL (100%).
- **Transformation Layer (dbt)**: 7 staging views, 6 intermediate models, 3 mart tables (`mart_customer_metrics`, `dim_customers`, `fact_orders`) with 95 dbt tests passing (100%).
- **Analytics & ML Layer**: RFM segmentation (`ml.rfm_segments`) and HistGradientBoosting Churn ML model (`ml.churn_predictions`) scoring 93,358 customers (100%).
- **FastAPI Domain & Analytical API Core (Phase 1)**: 23 endpoints serving portfolio KPIs, RFM distributions, revenue-at-risk tiers, time-series revenue trends, cohort retention survival decay, paginated customer listings, at-risk queues, 360° customer intelligence profiles, streaming CSV export, seller scorecards, and product catalog intelligence (100%).
- **Performance & Caching Layer (Phase 2)**: Thread-safe in-memory TTL caching with bypass support and tuned connection pooling (100%).
- **Verification Baseline**: 120 passing pytest tests across 9 test suites.

### Objective
Complete the remaining analytical endpoints, add low-latency caching, implement security and rate limiting, provide CSV campaign export, containerize with Docker, establish automated GitHub Actions CI/CD, and generate client integration contracts for React, Flutter, and Microsoft Power BI.

---

## 2. Roadmap Phases & Implementation Steps

```mermaid
graph TD
    subgraph Phase 1: Missing Endpoints
        E1[Revenue Trends Time-Series]
        E2[Cohort Retention Curves]
        E3[Seller Intelligence]
        E4[Product Intelligence]
        E5[CSV Export Engine]
    end

    subgraph Phase 2: Performance & Caching
        P1[In-Memory TTL Caching]
        P2[DB Connection Pool Tuning]
    end

    subgraph Phase 3: Hardening & Security
        S1[API Key & JWT Auth Middleware]
        S2[Rate Limiting]
        S3[Request Tracing & Metrics]
    end

    subgraph Phase 4: Containerization
        C1[Multi-Stage Dockerfile]
        C2[Docker Compose]
        C3[Cloud Deployment Descriptors]
    end

    subgraph Phase 5: CI/CD Pipeline
        CI1[GitHub Actions ci.yml]
        CI2[Automated Linting & Test Matrix]
    end

    subgraph Phase 6: Client Readiness
        R1[OpenAPI Contract Export]
        R2[Power BI Direct Query Guides]
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4 --> Phase 5 --> Phase 6
```

---

### Phase 1: Missing Domain & Analytical Endpoints (✅ Complete)

#### 1.1 Revenue Trends Time-Series (`GET /api/analytics/revenue`) (✅ Complete)
- **Route**: `GET /api/analytics/revenue?interval=month&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- **Data Source**: `mart.fact_orders` grouped by `DATE_TRUNC(:interval, purchased_at)`.
- **Response Shape**: `RevenueAnalyticsResponse` containing chronological `trends` list with `gmv`, `orders_count`, `delivered_count`, `avg_order_value`, `total_freight`, and `late_order_rate`.
- **Files**:
  - `backend/schemas/analytics.py` (`RevenueTrendPoint`, `RevenueAnalyticsResponse`)
  - `backend/services/analytics_service.py` (`get_revenue_trends`)
  - `backend/routers/analytics.py` (`GET /api/analytics/revenue`)
  - `tests/test_api.py` (`test_analytics_revenue_trends`)

#### 1.2 Customer Cohort Retention Analysis (`GET /api/analytics/retention`) (✅ Complete)
- **Route**: `GET /api/analytics/retention`
- **Data Source**: `mart.dim_customers` (first purchase month) joined to `mart.fact_orders` (order month) calculating survival rates ($M+0, M+1, \dots, M+12$).
- **Response Shape**: `RetentionAnalyticsResponse` containing `cohorts` list with `cohort_month`, `cohort_size`, and month-by-month `retention_rates` map.
- **Files**:
  - `backend/schemas/analytics.py` (`CohortRetentionPoint`, `RetentionAnalyticsResponse`)
  - `backend/services/analytics_service.py` (`get_cohort_retention`)
  - `backend/routers/analytics.py` (`GET /api/analytics/retention`)
  - `tests/test_api.py` (`test_analytics_cohort_retention`)

#### 1.3 Marketplace Seller Intelligence (`GET /api/sellers`, `GET /api/sellers/{id}`) (✅ Complete)
- **Routes**:
  - `GET /api/sellers?page=1&page_size=20&state=SP&sort_by=total_revenue`
  - `GET /api/sellers/{seller_id}`
- **Data Source**: `staging.stg_sellers`, `staging.stg_order_items`, `staging.stg_orders`, `staging.stg_order_reviews`.
- **Metrics**: Total orders fulfilled, items sold, gross merchandise value, average item value, delivery delay days, late delivery rate, and average review score.
- **Files**:
  - `backend/schemas/seller.py` (`SellerSummary`, `SellerDetail`, `SellerListResponse`)
  - `backend/services/seller_service.py` (`SellerService`)
  - `backend/routers/sellers.py` (`sellers_router`)
  - `backend/main.py` (Registered router)
  - `tests/test_sellers.py` (6 functional tests passing)

#### 1.4 Product Catalog Intelligence (`GET /api/products`, `GET /api/products/categories`) (✅ Complete)
- **Routes**:
  - `GET /api/products?page=1&page_size=20&category=health_beauty`
  - `GET /api/products/categories`
  - `GET /api/products/{product_id}`
- **Data Source**: `staging.stg_products`, `staging.stg_order_items`, `staging.stg_order_reviews`.
- **Metrics**: Units sold, orders count, total revenue, average unit price, customer review ratings, weight and package dimensions.
- **Files**:
  - `backend/schemas/product.py` (`ProductSummary`, `CategorySummary`, `ProductListResponse`, `CategoryListResponse`)
  - `backend/services/product_service.py` (`ProductService`)
  - `backend/routers/products.py` (`products_router`)
  - `backend/main.py` (Registered router)
  - `tests/test_products.py` (6 functional tests passing)

#### 1.5 CSV/Excel Campaign Export (`GET /api/customers/export`) (✅ Complete)
- **Route**: `GET /api/customers/export?risk_tier=High&segment=Champions&format=csv`
- **Behavior**: Streams formatted CSV with `customer_unique_id`, `state`, `city`, `lifetime_spend`, `lifetime_orders`, `recency_days`, `segment`, `churn_probability`, `risk_tier`, `revenue_at_risk`, `retention_priority`, and tailored `recommended_action`.
- **Files**:
  - `backend/services/customer_service.py` (`stream_customers_csv`)
  - `backend/routers/customers.py` (`export_customers_csv` using `StreamingResponse`)
  - `tests/test_api.py` (`test_export_customers_csv`)

---

### Phase 2: Performance & Caching Layer (✅ Complete)

#### 2.1 In-Memory TTL Caching (✅ Complete)
- Implemented thread-safe in-memory caching engine (`backend/cache.py`) protected by `threading.RLock` with configurable time-to-live (`CACHE_DEFAULT_TTL_SECONDS=300`, default 5 minutes).
- Monotonic clock-based expiration (`time.monotonic()`) preventing clock drift issues and LRU eviction when capacity (`max_size=5000`) is reached.
- Deterministic cache key generation with automatic filtering of transient request objects (`sqlalchemy.orm.Session`, `Request`, `Response`).
- First-class support for `?bypass_cache=true` query parameter across `/api/analytics/overview`, `/api/analytics/segments`, `/api/analytics/rfm`, and `/api/analytics/revenue-at-risk` to force fresh database recomputations.
- Cache telemetry endpoint `GET /api/analytics/cache/stats` and cache invalidation endpoint `POST /api/analytics/cache/clear`.
- Validated with 10 unit tests in `tests/test_cache.py`.

#### 2.2 Connection Pool Tuning (✅ Complete)
- Fine-tuned SQLAlchemy engine connection pool in `backend/database.py` and configurable via `backend/config.py`:
  - `pool_size=10` (from `DB_POOL_SIZE`)
  - `max_overflow=20` (from `DB_MAX_OVERFLOW`)
  - `pool_recycle=300` (from `DB_POOL_RECYCLE`)
  - `pool_timeout=30` (from `DB_POOL_TIMEOUT`)
  - `pool_pre_ping=True` (guarantees recovery from serverless idle connection drops cleanly).

---

### Phase 3: Production Hardening & API Security (✅ Complete)

#### 3.1 Security & Authentication Dependency (✅ Complete)
- Created `backend/security.py` with dual authentication support:
  - Header-based API key: `X-API-Key` validated against configurable `API_KEYS` in `backend/config.py`.
  - Bearer token: `Authorization: Bearer <token>` using pure standard-library HMAC-SHA256 JWT tokens (`create_access_token`, `decode_access_token`) with claim verification (`sub`, `exp`, `iat`, `iss`).
  - Configurable via `.env`: `REQUIRE_AUTH=false` for local development/testing (dev bypass) and `true` in staging/production.
  - Public endpoint exemption: `/`, `/health`, `/api/health`, `/docs`, `/redoc`, `/openapi.json`, and `/api/auth/token` remain accessible without credentials.
  - Added token issuance route `POST /api/auth/token` and caller inspection `GET /api/auth/me` in `backend/routers/auth.py`.

#### 3.2 Rate Limiting (✅ Complete)
- Built high-performance in-memory sliding-window rate limiter in `backend/rate_limit.py` using high-resolution monotonic timestamps (`time.monotonic()`) and `threading.RLock`.
- Configurable thresholds via `RATE_LIMIT_ENABLED` and `RATE_LIMIT_REQUESTS_PER_MINUTE` (default: 120 req/min).
- Client IP resolution extracts client IP respecting `X-Forwarded-For` (first proxy hop) and `X-Real-IP` with fallback to `request.client.host`.
- Returns standard HTTP 429 Too Many Requests with `Retry-After`, `X-RateLimit-Limit`, and `X-RateLimit-Remaining: 0` headers.

#### 3.3 Request Tracing & Performance Logging (✅ Complete)
- Implemented ASGI middleware `RequestTracingAndSecurityMiddleware` in `backend/middleware.py`:
  - Automatically generates unique UUID4 `X-Request-ID` or preserves incoming tracing header.
  - Measures request latency via `time.perf_counter()` and attaches `X-Process-Time` (e.g. `12.34ms`) to every response.
  - Emits structured access logs to `mercury.access` recording client IP, HTTP method, route, status code, latency, and request ID.
  - Intercepts unhandled 500 errors and ensures `X-Request-ID` is preserved in error response for distributed debugging.
- Validated with 18 comprehensive tests in `tests/test_security.py` covering tracing, rate limiting, token generation, and authentication enforcement.

---

### Phase 4: Containerization & Cloud Deployment (✅ Complete)

#### 4.1 Multi-Stage Production Dockerfile (✅ Complete)
- Created `Dockerfile` utilizing multi-stage architecture:
  - Base image: `python:3.13-slim`.
  - Stage 1 (`builder`): Compiles dependencies into isolated `/opt/venv` without leaving build compilers in the final layer.
  - Stage 2 (`runner`): Stripped minimal runtime copying `/opt/venv`, creating unprivileged non-root user `mercury` (UID 1000, GID 1000).
  - Container healthcheck (`HEALTHCHECK`): Queries `http://localhost:${PORT:-8000}/health` via `curl` with 30s interval, 5s timeout, and 3 retries.
  - Configured `.dockerignore` excluding `.git`, `.venv`, `.env`, local caches, raw dataset files, and dbt build outputs.

#### 4.2 Docker Compose Orchestration (✅ Complete)
- Created `docker-compose.yml`:
  - Configures the `backend` service with `ports: ["8000:8000"]`.
  - Binds `.env` environment file and sets default container runtime options.
  - Mounts `./backend` and `./ml` directories read-only for high-velocity local hot-reloading.
  - Includes container-level healthcheck probing `/health`.

#### 4.3 Cloud Deployment Descriptors (✅ Complete)
- Created `Procfile` for Heroku / Render / Railway:
  - `web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- Created `render.yaml` Infrastructure-as-Code blueprint for Render:
  - Declares web service `mercury-backend` with zero-downtime healthcheck pointing to `/health`.
  - Pre-populates environment schema with secure random key generation (`API_KEYS`, `JWT_SECRET_KEY`) and production settings.
- Documented full deployment guide in `docs/deployment.md`.
- Validated with 5 automated verification tests in `tests/test_deployment.py`.

---

### Phase 5: Automated CI/CD Pipeline (GitHub Actions) (✅ Complete)

#### 5.1 Continuous Integration (`.github/workflows/ci.yml`) (✅ Complete)
- Implemented automated GitHub Actions workflow triggered on push to `main`, all Pull Requests targeting `main`, and manual dispatch (`workflow_dispatch`).
- Quality gates and execution pipeline:
  1. Python 3.13 setup with pip caching via `actions/setup-python@v5`.
  2. Dependency installation: `pip install -r requirements.txt`.
  3. Lint checks: `ruff check backend/ ml/ tests/` (configured via `pyproject.toml`).
  4. Formatter checks: `ruff format --check backend/ ml/ tests/`.
  5. Test suite execution: `pytest tests/ -v` running all test suites.
- Configured project-level linting and formatting standards in `pyproject.toml`.
- Validated with 3 automated workflow verification tests in `tests/test_ci.py`.

---

### Phase 6: Client Integration & Schema Contracts (✅ Complete)

#### 6.1 Static OpenAPI & TypeScript Types (✅ Complete)
- Implemented `scripts/export_openapi.py` CLI script to dump standard OpenAPI 3.1 `openapi.json` (25 endpoints, 32 schemas) directly from the application instance without booting a running server.
- Generated static `openapi.json` at repository root.
- Generated end-to-end TypeScript interfaces `types/api.ts` (2,502 lines) via `npx openapi-typescript openapi.json -o types/api.ts` providing typed contracts for React and Flutter clients.
- Added `package.json` with `npm run codegen`, `npm run export:openapi`, and `npm run generate:types` automated scripts.

#### 6.2 Power BI Direct Query Documentation (✅ Complete)
- Authored comprehensive operational guide `docs/powerbi_setup.md`:
  - Detailed Neon PostgreSQL connection parameters (`ep-...-pooler.neon.tech`, `sslmode=require`, DirectQuery vs Import trade-offs).
  - Star-schema entity relationship configurations (`mart.dim_customers` -> `mart.fact_orders`, `mart.mart_customer_metrics`, `ml.rfm_segments`, `ml.churn_predictions`).
  - Production DAX metric formulas: Total GMV, Total Orders, AOV, Repeat Purchase Rate, Portfolio Revenue at Risk, VIP Retention Exposure, High Risk Customer Count, Late Delivery Rate, and Average Review Rating.
  - Report visual layouts and cloud scheduled refresh guidance.
- Validated with 6 automated verification tests in `tests/test_client_contracts.py`.

---

## 3. Success Metrics & Verification Checklist

| Metric | Target | Verification Method |
|:---|:---:|:---|
| **Test Suite Coverage** | > 120 tests | `pytest tests/` (100% pass rate) |
| **API Response Latency (Cached)** | < 30ms | `curl -w "%{time_total}\n"` on `/api/analytics/overview` |
| **API Response Latency (Query)** | < 150ms | Paginated queries on `/api/customers` |
| **Container Build** | Clean build, < 250MB | `docker build -t mercury-backend .` |
| **OpenAPI Compliance** | 100% compliant | `python scripts/export_openapi.py` validation |
