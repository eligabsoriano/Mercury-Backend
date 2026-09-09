# Mercury Backend Engineering Roadmap & Implementation Specification

This document defines the roadmap and engineering plan to advance the **Mercury Customer Intelligence & Retention Analytics Backend** from its current functional baseline (~80% completion) to full production maturity (100% completion).

---

## 1. Executive Summary & Baseline

### Current Completion Status: ~85% (Backend) / ~65% (Full Project)
- **Data & Migration Layer**: 11 raw tables, 3 views, 1.56M records in Neon PostgreSQL (100%).
- **Transformation Layer (dbt)**: 7 staging views, 6 intermediate models, 3 mart tables (`mart_customer_metrics`, `dim_customers`, `fact_orders`) with 95 dbt tests passing (100%).
- **Analytics & ML Layer**: RFM segmentation (`ml.rfm_segments`) and HistGradientBoosting Churn ML model (`ml.churn_predictions`) scoring 93,358 customers (100%).
- **FastAPI API Core & Caching**: 12 endpoints serving portfolio KPIs, RFM distributions, revenue-at-risk tiers, customer listings with faceted filters, at-risk queues, 360° customer intelligence profiles, and cache telemetry/flush (85%).
- **Performance & Caching Layer (Phase 2)**: Thread-safe in-memory TTL caching with bypass support and tuned connection pooling (100%).
- **Verification Baseline**: 105 passing pytest tests across 7 test suites.

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

### Phase 1: Missing Domain & Analytical Endpoints

#### 1.1 Revenue Trends Time-Series (`GET /api/analytics/revenue`)
- **Route**: `GET /api/analytics/revenue?interval=month&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
- **Data Source**: `mart.fact_orders` grouped by `DATE_TRUNC(:interval, purchased_at)`.
- **Response Shape**:
  ```json
  {
    "interval": "month",
    "total_periods": 24,
    "trends": [
      {
        "period": "2017-01",
        "gmv": 120350.40,
        "orders_count": 780,
        "delivered_count": 765,
        "avg_order_value": 154.29,
        "total_freight": 18240.10,
        "late_order_rate": 4.5
      }
    ]
  }
  ```
- **Files**:
  - `backend/schemas/analytics.py` (Add `RevenueTrendPoint`, `RevenueAnalyticsResponse`)
  - `backend/services/analytics_service.py` (Add `get_revenue_trends`)
  - `backend/routers/analytics.py` (Add route handler)
  - `tests/test_api.py` (Add test cases)

#### 1.2 Customer Cohort Retention Analysis (`GET /api/analytics/retention`)
- **Route**: `GET /api/analytics/retention`
- **Data Source**: `mart.dim_customers` (acquisition month) joined to `mart.fact_orders` (order month) to calculate month-by-month cohort survival percentages ($M+0, M+1, \dots, M+12$).
- **Response Shape**:
  ```json
  {
    "cohorts": [
      {
        "cohort_month": "2017-01",
        "cohort_size": 750,
        "retention_rates": {
          "m0": 100.0,
          "m1": 4.1,
          "m2": 2.8,
          "m3": 3.2
        }
      }
    ]
  }
  ```
- **Files**:
  - `backend/schemas/analytics.py` (Add `CohortRetentionPoint`, `RetentionAnalyticsResponse`)
  - `backend/services/analytics_service.py` (Add `get_cohort_retention`)
  - `backend/routers/analytics.py` (Add route handler)

#### 1.3 Marketplace Seller Intelligence (`GET /api/sellers`, `GET /api/sellers/{id}`)
- **Routes**:
  - `GET /api/sellers?page=1&page_size=20&state=SP&sort_by=total_revenue`
  - `GET /api/sellers/{seller_id}`
- **Data Source**: `raw.sellers`, `raw.order_items`, `raw.order_reviews`, `staging.stg_orders`.
- **Metrics**: Total orders fulfilled, gross merchandise value, average delivery delay, late shipment percentage, average review rating.
- **Files**:
  - `backend/schemas/seller.py` (New: `SellerSummary`, `SellerDetail`, `SellerListResponse`)
  - `backend/services/seller_service.py` (New: `SellerService`)
  - `backend/routers/sellers.py` (New: `sellers_router`)
  - `backend/main.py` (Register router)

#### 1.4 Product Catalog Intelligence (`GET /api/products`, `GET /api/products/categories`)
- **Routes**:
  - `GET /api/products?page=1&page_size=20&category=health_beauty`
  - `GET /api/products/categories`
- **Data Source**: `staging.stg_products`, `raw.order_items`, `staging.stg_order_reviews`.
- **Metrics**: Product sales velocity, revenue contribution, weight/volume metrics, review score distribution.
- **Files**:
  - `backend/schemas/product.py` (New: `ProductSummary`, `CategorySummary`, `ProductListResponse`)
  - `backend/services/product_service.py` (New: `ProductService`)
  - `backend/routers/products.py` (New: `products_router`)
  - `backend/main.py` (Register router)

#### 1.5 CSV/Excel Campaign Export (`GET /api/customers/export`)
- **Route**: `GET /api/customers/export?risk_tier=High&segment=Champions&format=csv`
- **Behavior**: Streams CSV records with `customer_unique_id`, `state`, `lifetime_spend`, `churn_probability`, `risk_tier`, `retention_priority`, and recommended action for CRM / marketing campaigns.
- **Files**:
  - `backend/routers/customers.py` (Streaming response using `fastapi.responses.StreamingResponse`)

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

### Phase 3: Production Hardening & API Security

#### 3.1 Security & Authentication Dependency
- Create `backend/security.py` with support for:
  - Header-based API key: `X-API-Key`
  - Bearer token: `Authorization: Bearer <token>`
  - Configurable via `.env`: `REQUIRE_AUTH=false` for local development, `true` in production.

#### 3.2 Rate Limiting
- Add rate limiting middleware to prevent endpoint flooding and protect database connection limits.

#### 3.3 Request Tracing & Performance Logging
- Add ASGI middleware to attach a unique `X-Request-ID` and calculate `X-Process-Time` (in milliseconds) for every request header.

---

### Phase 4: Containerization & Cloud Deployment

#### 4.1 Multi-Stage Production Dockerfile
- `Dockerfile`: Multi-stage build using `python:3.13-slim`.
- Installs production dependencies without compiler bloat.
- Runs as an unprivileged user `mercury` (UID 1000).
- Includes container `HEALTHCHECK` pointing to `/health`.

#### 4.2 Docker Compose Orchestration
- `docker-compose.yml`: Defines the `backend` service with environment file binding, port mapping `8000:8000`, and volume mounts for development.

#### 4.3 Cloud Deployment Descriptors
- `Procfile` for Heroku / Render / Railway: `web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- `render.yaml` infrastructure-as-code blueprint for automated zero-downtime deployment.

---

### Phase 5: Automated CI/CD Pipeline (GitHub Actions)

#### 5.1 Continuous Integration (`.github/workflows/ci.yml`)
- Triggered on push to `main` and all Pull Requests.
- Steps:
  1. Python 3.13 setup with pip caching.
  2. Lint checks: `ruff check backend/ ml/ tests/`.
  3. Formatter checks: `ruff format --check backend/ ml/ tests/`.
  4. Test suite: `pytest tests/ -v`.

---

### Phase 6: Client Integration & Schema Contracts

#### 6.1 Static OpenAPI & TypeScript Types
- Add `scripts/export_openapi.py` to dump `openapi.json` without booting a live server.
- Support `npx openapi-typescript openapi.json -o types/api.ts` for the React web dashboard and Flutter client schemas.

#### 6.2 Power BI Direct Query Documentation
- Add `docs/powerbi_setup.md` detailing connection strings, table relationships, and DAX metric formulas connecting Microsoft Power BI to Neon PostgreSQL.

---

## 3. Success Metrics & Verification Checklist

| Metric | Target | Verification Method |
|:---|:---:|:---|
| **Test Suite Coverage** | > 120 tests | `pytest tests/` (100% pass rate) |
| **API Response Latency (Cached)** | < 30ms | `curl -w "%{time_total}\n"` on `/api/analytics/overview` |
| **API Response Latency (Query)** | < 150ms | Paginated queries on `/api/customers` |
| **Container Build** | Clean build, < 250MB | `docker build -t mercury-backend .` |
| **OpenAPI Compliance** | 100% compliant | `python scripts/export_openapi.py` validation |
