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
               DATASETS (dataset/)
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
| **Database** | PostgreSQL 16 (Neon) | Relational storage for raw, staging, and analytics marts |
| **Ingestion** | Python 3.13, `psycopg2` | High-throughput bulk loading via PostgreSQL `COPY` |
| **Transformations** | `dbt-postgres` | Modular, test-driven SQL transformations (`staging`, `mart`) |
| **Analytics & ML** | `pandas`, `scikit-learn`, `numpy` | RFM quintile segmentation & supervised churn classification |
| **API** | `FastAPI`, `Pydantic v2`, `uvicorn` | Programmatic decision-support REST endpoints |
| **Reporting** | Microsoft Power BI | Executive KPI and customer retention dashboards |

---

## 📂 Repository Structure

```text
mercury/
├── backend/                  ← FastAPI application
│   ├── routers/              ← REST route handlers
│   ├── schemas/              ← Pydantic v2 request/response models
│   └── services/             ← Business logic and database queries
├── dataset/                  ← Raw Olist CSV directories (gitignored)
├── dbt/
│   └── mercury_analytics/    ← dbt transformation project
│       ├── macros/           ← Custom macros (e.g. generate_schema_name)
│       ├── models/
│       │   ├── staging/      ← 7 staging views + 53 data tests
│       │   ├── intermediate/ ← Customer order and friction rollups
│       │   └── marts/        ← Mart models (mart_customer_metrics)
│       ├── dbt_project.yml   ← dbt project configuration
│       └── profiles.yml.example
├── docs/                     ← In-depth technical & business documentation
│   ├── architecture.md       ← Full system flow, data models, and API surface
│   ├── methodology.md        ← RFM scoring, churn definitions, ML features
│   ├── business_case.md      ← Retention matrix and SDG alignment
│   └── bi_reporting.md       ← Power BI dashboards & client app specs
├── etl/
│   └── ingest.py             ← High-performance raw CSV ingestion runner
├── ml/                       ← Feature engineering, RFM scoring, churn modeling
│   └── artifacts/            ← Trained serialized models (gitignored)
├── sql/
│   ├── schema.sql            ← PostgreSQL DDL for raw.* tables and indexes
│   ├── views.sql             ← Helper views (vw_ingestion_summary, etc.)
│   └── migrate.py            ← Automated database migration runner
└── requirements.txt          ← Pinned Python dependencies
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

### 3. Apply PostgreSQL Schema Migrations
```bash
python sql/migrate.py
```

### 4. Bulk Ingest Raw CSV Datasets
```bash
# Ingests both Olist E-Commerce and Marketing Funnel datasets:
python etl/ingest.py
```

### 5. Run & Test dbt Transformations
```bash
cd dbt/mercury_analytics
cp profiles.yml.example profiles.yml   # or build profiles.yml from .env
dbt run --select staging --profiles-dir .
dbt test --select staging --profiles-dir .
```

---

## 📚 Detailed Documentation

For comprehensive guides and mathematical methodologies, explore:
- [docs/architecture.md](file:///Users/gab/Documents/GitHub/Mercury-Backend/docs/architecture.md) — System flow, schema dictionaries, and API contract.
- [docs/methodology.md](file:///Users/gab/Documents/GitHub/Mercury-Backend/docs/methodology.md) — RFM distribution, time-bounded churn definitions, and revenue-at-risk formulas.
- [docs/business_case.md](file:///Users/gab/Documents/GitHub/Mercury-Backend/docs/business_case.md) — The retention dilemma, prioritization matrix, and UN SDG alignment.
- [docs/bi_reporting.md](file:///Users/gab/Documents/GitHub/Mercury-Backend/docs/bi_reporting.md) — Executive, Retention, and Seller dashboard specifications.

---

## 👤 Author & Vision

**Eli Gabriel T. Soriano** — BS Information Technology (System Development)  
*Specialization: Data Analytics, Data Engineering, Machine Learning & Backend Engineering.*

> **Vision**: Empower businesses to identify valuable customers, anticipate churn risk, understand financial exposure, and execute precision retention strategies.