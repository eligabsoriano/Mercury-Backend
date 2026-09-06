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

### Intermediate models (views in `intermediate` schema)  ← Phase 4
- `int_customer_orders` — one row per customer_unique_id with order history

### Mart models (tables in `mart` schema)  ← Phase 4
- `mart_customer_metrics` — RFM scores, churn inputs, revenue at risk

## API Surface (backend/)

Planned FastAPI endpoints:

```text
GET /api/customers
GET /api/customers/{id}
GET /api/customers/segments
GET /api/customers/at-risk
GET /api/analytics/revenue
GET /api/analytics/retention
GET /api/analytics/rfm
GET /api/analytics/revenue-at-risk
GET /api/products
GET /api/sellers
```

## Technology Stack

| Area | Technology |
|------|-----------|
| Data ingestion | Python, Pandas |
| Database | PostgreSQL (Neon) |
| Transformation | dbt-postgres |
| Analytics / ML | Python, scikit-learn, Matplotlib |
| API | FastAPI, Pydantic v2 |
| Web | React, TypeScript, Tailwind CSS |
| Mobile | Flutter, Dart |
| BI | Microsoft Power BI |
| DevOps | Docker, GitHub Actions |

## Project Structure

```text
mercury/
├── backend/              ← FastAPI app
│   ├── routers/
│   ├── schemas/
│   └── services/
├── data/
│   ├── raw/              ← gitignored
│   └── processed/        ← gitignored
├── dbt/
│   └── mercury_analytics/
│       ├── models/
│       │   ├── staging/
│       │   ├── intermediate/
│       │   └── marts/
│       ├── tests/
│       ├── macros/
│       ├── dbt_project.yml
│       ├── profiles.yml         ← gitignored (real credentials)
│       └── profiles.yml.example ← committed (template)
├── docs/                 ← this file and methodology.md
├── etl/                  ← CSV ingestion scripts
├── ml/                   ← RFM, churn, revenue-at-risk
│   └── artifacts/        ← gitignored
├── notebooks/            ← exploratory analysis
├── sql/                  ← schema.sql, views.sql, migrate.py
├── tests/                ← pytest suite
├── ai/                   ← agent context files
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```
