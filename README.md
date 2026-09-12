# Mercury — Customer Intelligence & Retention Analytics

**Mercury** is a customer intelligence and retention analytics backend platform designed for e-commerce enterprises. It transforms raw transactional and operational logs into actionable customer segments, predictive churn probabilities, revenue-at-risk forecasts, and prioritized retention workflows.

---

## 🎯 What Mercury Does

Raw transaction records record what was sold, but they do not reveal:
- Which customers generate long-term value vs. one-time volume.
- Which high-value customers are silently drifting toward defection.
- The financial exposure ($) of customer attrition.
- How retention interventions should be prioritized given finite marketing and operational resources.

Mercury unifies **PostgreSQL**, **dbt**, **scikit-learn**, and **FastAPI** to deliver an automated end-to-end customer intelligence pipeline.

---

## 🏗️ System Architecture

```text
               DATASETS (data/)
     Olist Brazilian E-Commerce (9 CSVs)
     Marketing Funnel Deals & MQL (2 CSVs)
                       │
                       ▼
             Raw Ingestion (etl/ingest.py)
                       │  PostgreSQL COPY streaming
                       ▼
           Neon PostgreSQL (raw.* schemas)
                       │
                       ▼
         dbt Layer (dbt/mercury_analytics/)
     ├── staging/      ← Type casting, field aliases, delivery delays
     ├── intermediate/ ← Customer aggregation (customer_unique_id)
     └── marts/        ← Analytical tables (RFM, churn signals)
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
       Python ML (ml/)       FastAPI (backend/)
   RFM & Churn Modeling      High-speed REST API
             │                   │
             └─────────┬─────────┘
                       ▼
              Web, Mobile & Power BI
```

> [!IMPORTANT]
> **Customer Key Resolution**: In the Olist dataset, `customer_id` is order-scoped (one per order). The true returning customer key is `customer_unique_id`. All customer metrics, RFM segmentation, and churn modeling aggregate strictly on `customer_unique_id`.

---

## 🧰 Technology Stack

| Layer | Technology | Role |
|:---|:---|:---|
| **Database** | PostgreSQL 16 (Neon) | Serverless relational storage for raw, staging, and analytics marts |
| **Ingestion** | Python 3.13, `psycopg2` | High-throughput bulk loading via PostgreSQL `COPY` |
| **Transformations** | `dbt-postgres` | Modular, test-driven SQL transformations (`staging`, `intermediate`, `mart`) |
| **Analytics & ML** | `pandas`, `scikit-learn`, `numpy` | RFM quintile segmentation & supervised churn classification |
| **API & Security** | `FastAPI`, `Pydantic v2`, `uvicorn` | 39 REST endpoints with `X-API-Key` & Bearer JWT auth, rate limiting |
| **Client Types** | TypeScript, OpenAPI 3.1 | Auto-generated type contracts (`types/api.ts`) for React & Flutter |
| **Reporting** | Microsoft Power BI | DirectQuery star-schema dashboards & production DAX retention formulas |
| **DevOps & CI/CD** | Docker, Docker Compose, GitHub Actions, Ruff | Containerization, local orchestration, and automated CI quality gates |

---

## 📂 Repository Structure

```text
mercury/
├── .github/workflows/ci.yml   ← Automated GitHub Actions CI pipeline (Python 3.13, Ruff, Pytest)
├── backend/                   ← FastAPI application (39 live endpoints)
│   ├── cache.py               ← Thread-safe in-memory TTL caching engine
│   ├── config.py              ← Runtime environment configuration
│   ├── database.py            ← Tuned SQLAlchemy engine pool & health diagnostics
│   ├── main.py                ← FastAPI app entrypoint, middleware, routers
│   ├── middleware.py          ← X-Request-ID, X-Process-Time, access logs, 500 handler
│   ├── rate_limit.py          ← In-memory sliding-window rate limiter (120 req/min)
│   ├── security.py            ← API Key & HMAC-SHA256 JWT auth dependencies
│   ├── routers/               ← Analytics, Customers, Products, Sellers, Retention, Marketing, Auth, Health
│   ├── schemas/               ← Pydantic v2 request/response models
│   └── services/              ← Analytics, customer, seller, marketing, prediction, and retention services
├── dbt/
│   └── mercury_analytics/     ← dbt transformation project
│       ├── macros/            ← Custom schema name generator macros
│       ├── models/
│       │   ├── staging/       ← 9 staging views + 71 data tests
│       │   ├── intermediate/  ← 6 customer-level aggregation rollups
│       │   └── marts/         ← 6 analytics marts (mart_customer_metrics, dim_customers, fact_orders, mart_product_metrics, mart_seller_metrics, mart_marketing_funnel)
│       └── dbt_project.yml
├── docs/                      ← In-depth technical & business documentation
│   ├── architecture.md        ← Full system flow, data models, and API surface
│   ├── backend_roadmap.md     ← Complete backend engineering roadmap (Phases 1-11)
│   ├── business_case.md       ← The retention dilemma, prioritization matrix, and SDG alignment
│   ├── deployment.md          ← Docker, Docker Compose, and Cloud PaaS operations guide
│   ├── methodology.md         ← RFM scoring, churn definitions, and ML feature matrix
│   └── powerbi_setup.md       ← Power BI DirectQuery connection, star-schema, and DAX formulas
├── etl/
│   └── ingest.py              ← High-performance raw CSV ingestion runner
├── ml/                        ← Feature engineering, RFM scoring, churn modeling
│   └── artifacts/             ← Serialized model artifacts (churn_model.joblib)
├── scripts/
│   └── export_openapi.py      ← Programmatic OpenAPI 3.1 schema exporter
├── sql/
│   ├── schema.sql             ← PostgreSQL DDL for raw.* tables and indexes
│   ├── views.sql              ← Helper views (vw_ingestion_summary, etc.)
│   └── migrate.py             ← Automated database migration runner
├── tests/                     ← Comprehensive 192-test automated test suite (15 modules)
├── types/
│   └── api.ts                 ← Auto-generated TypeScript types (4,237 lines)
├── Dockerfile                 ← Multi-stage production container (python:3.13-slim, user mercury)
├── docker-compose.yml         ← Multi-container local development orchestration
├── openapi.json               ← Static OpenAPI 3.1 schema specification
├── package.json               ← Client SDK codegen scripts (npm run codegen)
├── Procfile                   ← PaaS process descriptor (Render / Railway / Heroku)
├── pyproject.toml             ← Ruff linter/formatter configurations
├── pytest.ini                 ← Pytest test runner settings
├── render.yaml                ← Infrastructure-as-code deployment blueprint for Render
└── requirements.txt           ← Pinned production and tooling dependencies
```

---

## 🚀 Quickstart & Setup

### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Credentials
```bash
cp .env.example .env
# Edit .env and supply your Neon PostgreSQL DATABASE_URL
```

### 3. Run FastAPI Backend Locally
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
# Interactive documentation available at:
# Swagger UI: http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
```

### 4. Run Automated Test Suite (192 Tests)
```bash
# Runs 154 offline unit/mock tests (38 live DB tests are cleanly skipped when DATABASE_URL is unset)
pytest tests/ -v
```

### 5. Run Linter & Formatter (Ruff)
```bash
ruff check backend/ ml/ tests/ scripts/
ruff format --check backend/ ml/ tests/ scripts/
```

### 6. Client SDK Codegen (OpenAPI & TypeScript)
```bash
# Exports openapi.json and generates types/api.ts:
npm run codegen
```

### 7. Run with Docker Compose
```bash
docker compose up -d
docker compose logs -f backend
```

---

## 📚 Detailed Documentation

For comprehensive guides and mathematical methodologies, explore:
- [docs/architecture.md](docs/architecture.md) — System flow, schema dictionaries, and 39-endpoint API contract.
- [docs/backend_roadmap.md](docs/backend_roadmap.md) — Full engineering roadmap (Phases 1-11 with Phase 10 active).
- [docs/deployment.md](docs/deployment.md) — Production Docker, Docker Compose, Render, and Railway deployment instructions.
- [docs/powerbi_setup.md](docs/powerbi_setup.md) — Power BI DirectQuery connection parameters, star-schema model, and DAX metric formulas.
- [docs/methodology.md](docs/methodology.md) — RFM quintile distribution, time-bounded churn definitions, and revenue-at-risk mathematics.
- [docs/business_case.md](docs/business_case.md) — The retention dilemma, prioritization matrix, and SDG alignment.

---

## 👤 Author & Vision

**Eli Gabriel T. Soriano** — BS Information Technology (System Development)  
*Specialization: Data Analytics, Data Engineering, Machine Learning & Backend Engineering.*

> **Vision**: Empower businesses to identify valuable customers, anticipate churn risk, understand financial exposure, and execute precision retention strategies.