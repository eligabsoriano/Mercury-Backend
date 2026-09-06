# Mercury Codebase Map

Last updated: 2026-09-06 (PostgreSQL Olist Schema & dbt Staging Scaffolding Complete)

## Directory Structure

```text
mercury/
├── backend/              ← FastAPI app: routes, schemas, services, DB access
│   ├── routers/          ← Route handlers (customers, analytics, products, sellers)
│   ├── schemas/          ← Pydantic v2 request/response models
│   └── services/         ← Business logic and database access layer
├── data/
│   ├── raw/              ← Raw Olist CSVs (gitignored)
│   └── processed/        ← Processed outputs / intermediate data (gitignored)
├── dbt/
│   └── mercury_analytics/← dbt transformation project (dbt-postgres)
│       ├── models/
│       │   ├── staging/  ← 7 staging models (stg_customers, stg_orders, etc.)
│       │   ├── intermediate/ ← Planned customer-level rollup models
│       │   └── marts/    ← Planned analytical marts (mart_customer_metrics, etc.)
│       ├── tests/        ← Custom generic / singular dbt tests
│       ├── macros/       ← dbt macros
│       ├── dbt_project.yml
│       ├── profiles.yml.example
│       └── profiles.yml  ← Local active connection (gitignored)
├── docs/                 ← Architecture, data dictionary, and methodology documentation
├── etl/                  ← Raw CSV ingestion into PostgreSQL (raw & raw_marketing)
├── ml/
│   └── artifacts/        ← Trained model artifacts (.joblib / .pkl) (gitignored)
├── notebooks/            ← Exploratory data analysis notebooks
├── sql/                  ← PostgreSQL raw DDL schema, helper views, and migration runner
│   ├── schema.sql        ← raw.* and raw_marketing.* tables + indexes
│   ├── views.sql         ← Helper views (vw_delivered_orders, etc.)
│   └── migrate.py        ← Re-runnable migration runner
├── tests/                ← Pytest test suite
├── ai/                   ← AI pair programming context, state, decisions, and maps
├── .env.example          ← Template for DATABASE_URL and service config
├── .gitignore            ← Protects secrets, local CSVs, dbt artifacts, and models
├── requirements.txt      ← Python dependencies (FastAPI, dbt-postgres, psycopg2, etc.)
└── README.md             ← Project overview and executive documentation
```

## Implementation Status by Area

| Directory | Area | Status | Notes |
|:---|:---|:---|:---|
| `sql/` | Database DDL & Migrations | ✅ Active | Migrations verified on Neon; 11 tables and 16 views active |
| `etl/` | Raw Data Ingestion | ✅ Active | `etl/ingest.py` loaded 1.56M rows across all 11 tables |
| `dbt/` | Transformation Layer | ✅ Active | 16 models materialized (staging, intermediate, mart), 95 tests pass |
| `tests/` | Automated Test Suite | ✅ Active | Pytest suite: 19 tests passing (schemas, ETL, dbt staging & marts) |
| `ml/` | Analytics & ML Models | ⏳ Next | Phase 5 RFM scoring, Phase 6 churn modeling & revenue-at-risk |
| `backend/`| FastAPI Service | ⏳ Pending | Pydantic models & REST API endpoints |
| `notebooks/`| Exploratory Analysis | ⏳ Pending | EDA on Olist dataset |

## Analytical Data Flow

```text
Olist CSVs (9 primary + 2 marketing)
                 │
                 ▼
         Python ETL (etl/)
                 │
                 ▼
       PostgreSQL (raw schema)
                 │
                 ▼
     dbt Staging (staging schema)
                 │
                 ▼
      dbt Marts (mart schema)
    (grouped by customer_unique_id)
                 │
         ┌───────┴───────┐
         ▼               ▼
     Python ML      FastAPI API
 (RFM & Churn)     (backend/)
                         │
                         ▼
                  React / Power BI
```