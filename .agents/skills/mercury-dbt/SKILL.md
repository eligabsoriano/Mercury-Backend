---
name: mercury-dbt
description: >-
  Runbook for compiling, testing, and running dbt transformations in Mercury Analytics
  across staging, intermediate, and analytical mart layers against PostgreSQL.
---

# Mercury dbt Transformation Runbook

This skill outlines the conventions, structure, and execution workflows for dbt models in the Mercury customer intelligence pipeline.

## Project Layout

All dbt configuration and SQL models reside in `dbt/mercury_analytics/`:

- `models/staging/`: 9 staging views cleaning raw Olist tables (type casting, English translation aliases, boolean flags, marketing leads, closed deals).
- `models/intermediate/`: 6 intermediate rollups aggregated strictly by `customer_unique_id` (orders, locations, fulfillment delays, reviews).
- `models/marts/`: 6 analytical marts:
  - `mart_customer_metrics.sql` (central Customer Intelligence table with RFM base metrics, tenure, fulfillment, reviews)
  - `dim_customers.sql` (star-schema customer dimension)
  - `fact_orders.sql` (star-schema order fact)
  - `mart_product_metrics.sql` (product catalog performance, GMV, orders, review scores)
  - `mart_seller_metrics.sql` (seller performance, fulfillment velocity, delays, review ratings)
  - `mart_marketing_funnel.sql` (seller acquisition attribution, conversion cycle, and realized marketplace revenue)
- `macros/`: Custom schema name generator (`generate_schema_name.sql`).
- `dbt_project.yml`: Core project definitions and target schemas (`staging`, `intermediate`, `mart`).

## Execution Workflows

Always execute dbt commands within `dbt/mercury_analytics` or pass `--project-dir`:

```bash
# 1. Compile models without connecting to live DB (syntax & Jinja validation)
dbt compile --project-dir dbt/mercury_analytics

# 2. Run dbt tests against configured database
dbt test --project-dir dbt/mercury_analytics

# 3. Run a specific mart model
dbt run --project-dir dbt/mercury_analytics --select mart_customer_metrics

# 4. Run staging models only
dbt run --project-dir dbt/mercury_analytics --select staging.*
```

## Guidelines & Guardrails

1. **Schema Isolation**: Never write custom tables to `raw`. Staging creates views in `staging`, intermediate views in `intermediate`, and marts build materialized tables in `mart`.
2. **Customer Identity Grain**: Intermediate rollups and `mart_customer_metrics` must aggregate strictly by `customer_unique_id`, never `customer_id` (which is an order-scoped surrogate).
3. **Null Handling**: Ensure `COALESCE` is used on numeric aggregates (`total_spend`, `freight_value`, `late_delivery_count`) to avoid propagating nulls into downstream ML features.
4. **Idempotence**: Models should be deterministic and idempotent. Do not use non-deterministic date functions unless parameterized via dbt variables.
