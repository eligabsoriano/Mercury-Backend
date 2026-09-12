# Architecture and Implementation

## System Flow

```text
Olist Brazilian E-Commerce CSVs (9 files)          Marketing Funnel CSVs (2 files, optional)
              │                                                    │
              └──────────────────┬─────────────────────────────────┘
                                 ▼
                    Python ingestion (etl/)
                                 │
                                 ▼
                   Neon PostgreSQL — raw schema
                   raw.customers, raw.orders,
                   raw.order_items, raw.order_payments,
                   raw.order_reviews, raw.products,
                   raw.sellers, raw.geolocation,
                   raw.category_translations
                   raw_marketing.mql, raw_marketing.closed_deals
                                 │
                                 ▼
                    dbt (dbt/mercury_analytics/)
                    ├── staging/   ← cleaned, renamed columns
                    ├── intermediate/ ← business logic joins
                    └── marts/     ← final analytics tables
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                   ▼
      Python / RFM          ML models            Power BI
       (ml/rfm.py)      (ml/train.py)           dashboard
              │                  │
              └──────────────────┘
                                 ▼
                            FastAPI (backend/)
                                 │
                     ┌───────────┴───────────┐
                     ▼                       ▼
                  Web App               Mobile App
                (React/TS)           (Flutter/Dart)
```

## Key Architecture Decision: customer_id vs customer_unique_id

In the Olist dataset, `customer_id` is **order-scoped** — each order gets a distinct
`customer_id`. The true returning-customer key is `customer_unique_id`.

All RFM segmentation, churn prediction, and customer metrics must be computed
on `customer_unique_id`. This is enforced in dbt's intermediate models.

## Data Model (raw schema)

The raw ingestion layer preserves source column names exactly.

| Table                          | Rows      | Key                     |
|-------------------------------|-----------|-------------------------|
| `raw.customers`                | 99,441    | customer_id (order-scoped) |
| `raw.orders`                   | 99,441    | order_id                |
| `raw.order_items`              | 112,650   | (order_id, order_item_id) |
| `raw.order_payments`           | 103,886   | (order_id, payment_sequential) |
| `raw.order_reviews`            | 99,224    | review_id               |
| `raw.products`                 | 32,951    | product_id              |
| `raw.sellers`                  | 3,095     | seller_id               |
| `raw.geolocation`              | 1,000,163 | zip prefix (not unique) |
| `raw.category_translations`    | 71        | product_category_name   |
| `raw_marketing.mql`            | 8,000     | mql_id                  |
| `raw_marketing.closed_deals`   | 842       | mql_id                  |

## dbt Layer (dbt/mercury_analytics/)

### Staging models (views in `staging` schema)
- `stg_customers` — resolves customer_id / customer_unique_id ambiguity
- `stg_orders` — delivered orders only, cleaned timestamps, delivery_delay_days
- `stg_order_items` — item_revenue = price + freight_value
- `stg_order_payments` — order-level aggregation with primary_payment_type
- `stg_order_reviews` — is_negative_review / is_positive_review flags
- `stg_products` — English category name joined in, typo aliases
- `stg_sellers` — normalised city/state casing

### Intermediate models (views in `intermediate` schema)
- `int_order_items_aggregated` — order-level aggregation of items, price, freight, and product variety
- `int_order_reviews_aggregated` — order-level aggregation of customer review ratings and flags
- `int_customer_locations` — deterministic primary location per `customer_unique_id`
- `int_customer_orders` — order history rollup per `customer_unique_id` (orders, spend, AOV)
- `int_customer_fulfillment` — delivery delay days and late delivery friction metrics
- `int_customer_reviews` — customer satisfaction feedback and negative review ratios

### Mart models (tables in `mart` schema)
- `mart_customer_metrics` (93,358 rows) — central Customer Intelligence table aggregated strictly by `customer_unique_id` with RFM base metrics, recency_days, delivery delay, and review sentiment
- `dim_customers` (93,358 rows) — star-schema dimension table with primary location, tenure, and repeat buyer flag
- `fact_orders` (96,478 rows) — star-schema order fact table linking order lifecycle, items, payments, and reviews
- `mart_product_metrics` (32,951 rows) — product-level catalog performance, orders, units sold, GMV, average price, review scores, and repeat customer volume
- `mart_seller_metrics` (3,095 rows) — seller-level fulfillment velocity, total orders, GMV, average delivery delay days, and customer satisfaction metrics

## Performance & In-Memory Caching Layer (`backend/cache.py`)

- **Thread-Safe In-Memory Cache**: High-throughput memory cache synchronized via `threading.RLock` and monotonic clock timestamps (`time.monotonic()`) preventing wall-clock drift.
- **LRU Capacity Protection**: Automatically prunes expired records and enforces an upper ceiling (`max_size=5000`) using LRU eviction.
- **Cache Invalidation & Bypass**: Every analytical route supports `?bypass_cache=true` for on-demand re-querying. Operations can clear the cache via `POST /api/analytics/cache/clear`.
- **Database Connection Pool Tuning**: SQLAlchemy engine fine-tuned for serverless PostgreSQL (`pool_size=10`, `max_overflow=20`, `pool_recycle=300`, `pool_timeout=30`, `pool_pre_ping=True`).

## Security, Rate Limiting & Tracing (`backend/security.py`, `backend/rate_limit.py`, `backend/middleware.py`)

- **Dual-Scheme Authentication**:
  - `X-API-Key` header verified against pre-shared keys using constant-time comparisons (`hmac.compare_digest`).
  - Bearer token: `Authorization: Bearer <token>` using pure Python standard library HMAC-SHA256 JWT tokens.
  - Configurable: `REQUIRE_AUTH=false` for local dev/testing; `true` in production.
  - Public endpoints (`/`, `/health`, `/api/health`, `/docs`, `/redoc`, `/openapi.json`, `/api/auth/token`) are exempted.
- **In-Memory Rate Limiting**: Sliding-window counter with monotonic timestamps returning HTTP 429 Too Many Requests and `Retry-After` header when requests exceed 120 req/min per IP.
- **Request Tracing & Latency Headers**: Attaches unique `X-Request-ID` (UUID4) and `X-Process-Time` (in milliseconds) to all HTTP responses. Structured access logs emitted under `mercury.access`.

## API Surface (backend/ — 25 Live Endpoints)

| Category | Method & Path | Description |
|:---|:---|:---|
| **System** | `GET /` | API Root and navigation directory index |
| **System** | `GET /health` | System health check and database latency ping |
| **System** | `GET /api/health` | Diagnostic health alias |
| **Auth** | `POST /api/auth/token` | Issue signed HMAC-SHA256 JWT Bearer access token |
| **Auth** | `GET /api/auth/me` | Inspect authenticated caller identity and scopes |
| **Analytics** | `GET /api/analytics/overview` | Macro portfolio KPIs (GMV, AOV, repeat rate, RAR) |
| **Analytics** | `GET /api/analytics/segments` | RFM customer segment distribution and spend |
| **Analytics** | `GET /api/analytics/rfm` | RFM segment summary alias |
| **Analytics** | `GET /api/analytics/revenue-at-risk` | Financial exposure across churn risk tiers |
| **Analytics** | `GET /api/analytics/revenue` | Chronological revenue, orders, AOV time-series |
| **Analytics** | `GET /api/analytics/retention` | Monthly customer cohort retention survival curves |
| **Cache** | `GET /api/analytics/cache/stats` | In-memory TTL cache telemetry & hit ratio |
| **Cache** | `POST /api/analytics/cache/clear` | Purge active analytics cache entries |
| **Customers** | `GET /api/customers` | Paginated customer listings with multi-attribute filtering |
| **Customers** | `GET /api/customers/at-risk` | Actionable retention queue sorted by RAR descending |
| **Customers** | `GET /api/customers/export` | Streaming CSV download with retention action playbooks |
| **Customers** | `GET /api/customers/segments` | RFM customer segmentation summary convenience alias |
| **Customers** | `GET /api/customers/{id}` | Customer 360 profile (orders, friction, RFM, churn) |
| **Customers** | `GET /api/customers/{id}/rfm` | Individual customer RFM scorecard |
| **Customers** | `GET /api/customers/{id}/churn` | Individual churn probability & risk tier scorecard |
| **Products** | `GET /api/products` | Paginated catalog search with category & rating filters |
| **Products** | `GET /api/products/categories` | Product category breakdown with sales & review scores |
| **Products** | `GET /api/products/{id}` | Product 360 scorecard with specs & revenue metrics |
| **Sellers** | `GET /api/sellers` | Paginated marketplace seller scorecard & rankings |
| **Sellers** | `GET /api/sellers/{id}` | Individual seller 360 profile with top categories |
| **Docs** | `GET /docs`, `/redoc`, `/openapi.json` | Interactive Swagger UI, ReDoc, and OpenAPI spec |

## Client Interfaces & Downstream Contracts

Client applications consume typed API contracts synchronized from the FastAPI OpenAPI 3.1 specification:
- **OpenAPI 3.1 Spec**: [openapi.json](../openapi.json) (exported via `python scripts/export_openapi.py`).
- **TypeScript Interface Definitions**: [types/api.ts](../types/api.ts) (2,502 lines generated via `npm run codegen`).

### Consumer Applications
- **Web Application (`Mercury-Web`)**: Built with React, TypeScript, and Tailwind CSS. Features Executive Overview KPIs, Customer Intelligence Directory, Customer 360 Deep-Dive, and Action Workspace for retention list export (`GET /api/customers/export`).
- **Mobile Application**: Built with Flutter and Dart for on-the-go decision support, high-risk churn alerts, and on-demand customer lookup.
- **Power BI Dashboards**: DirectQuery analytics on Neon PostgreSQL star-schema (`dim_customers`, `fact_orders`, `mart_customer_metrics`). See [docs/powerbi_setup.md](powerbi_setup.md).

## Technology Stack

| Area | Technology |
|------|-----------|
| Data ingestion | Python, Pandas, psycopg2 (`COPY` bulk stream) |
| Database | PostgreSQL 16 (Neon serverless with connection pooling) |
| Transformation | dbt-postgres (`staging`, `intermediate`, `mart`) |
| Analytics / ML | Python, scikit-learn (`HistGradientBoosting`), joblib |
| API & Security | FastAPI, Pydantic v2, uvicorn, standard library HMAC-SHA256 JWT |
| Web Client | React, TypeScript, Tailwind CSS |
| Mobile Client | Flutter, Dart |
| BI & Reporting | Microsoft Power BI (DirectQuery & Star-Schema) |
| DevOps & CI/CD | Docker, Docker Compose, GitHub Actions, Ruff, Render |

## Project Structure

```text
mercury/
├── .github/
│   └── workflows/
│       └── ci.yml            ← GitHub Actions CI pipeline (Python 3.13, Ruff, Pytest)
├── backend/                  ← FastAPI application
│   ├── cache.py              ← Thread-safe in-memory TTL caching engine
│   ├── config.py             ← Runtime environment configurations
│   ├── database.py           ← SQLAlchemy engine with tuned pool & health checks
│   ├── main.py               ← App entrypoint, middleware, router registrations
│   ├── middleware.py         ← X-Request-ID, X-Process-Time, access logging, 500 handler
│   ├── rate_limit.py         ← Sliding-window in-memory rate limiter
│   ├── security.py           ← Dual API Key & HMAC-SHA256 JWT auth dependencies
│   ├── routers/              ← Modular REST route handlers
│   ├── schemas/              ← Pydantic v2 validation models
│   └── services/             ← Business query services (Analytics, Customer, Seller, Product)
├── dbt/
│   └── mercury_analytics/    ← dbt transformation project
│       ├── models/
│       │   ├── staging/      ← 7 staging views + 53 data tests
│       │   ├── intermediate/ ← 6 intermediate customer rollups
│       │   └── marts/        ← 5 mart tables (mart_customer_metrics, dim_customers, fact_orders, mart_product_metrics, mart_seller_metrics)
│       ├── macros/           ← Custom schema name generator macros
│       └── dbt_project.yml
├── docs/                     ← System documentation
│   ├── architecture.md       ← Full system flow, data models, and API surface
│   ├── backend_roadmap.md    ← Complete backend development roadmap (all 7 phases complete)
│   ├── business_case.md      ← Retention dilemma and SDG business justification
│   ├── deployment.md         ← Docker, Docker Compose, and Cloud PaaS operations guide
│   ├── methodology.md        ← RFM quintile scoring and ML churn methodology
│   └── powerbi_setup.md      ← Power BI DirectQuery connection, star-schema, and DAX formulas
├── etl/                      ← CSV bulk ingestion runner
├── ml/                       ← Feature engineering, RFM scoring, churn modeling
│   └── artifacts/            ← Serialized model artifacts (churn_model.joblib)
├── scripts/
│   └── export_openapi.py     ← Static OpenAPI 3.1 schema exporter
├── sql/                      ← DDL schema, views, and migration runner
├── tests/                    ← Comprehensive 152-test automated test suite (13 modules)
├── types/
│   └── api.ts                ← Auto-generated TypeScript types (2,502 lines)
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile                ← Multi-stage production container (python:3.13-slim, user mercury)
├── docker-compose.yml        ← Multi-container local development orchestration
├── openapi.json              ← Static OpenAPI 3.1 schema specification
├── package.json              ← Client SDK codegen scripts (npm run codegen)
├── Procfile                  ← PaaS process descriptor (Render / Railway / Heroku)
├── pyproject.toml            ← Ruff linter/formatter configurations
├── pytest.ini                ← Test runner settings
├── render.yaml               ← Infrastructure-as-code deployment blueprint for Render
└── requirements.txt          ← Pinned production and tooling dependencies
```
