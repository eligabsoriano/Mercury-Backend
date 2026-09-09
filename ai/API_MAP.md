# Mercury API Map

Last updated: 2026-09-06 (FastAPI Surface for Olist Dataset)

The planned FastAPI REST endpoints connect web and mobile clients to PostgreSQL/dbt marts and ML predictions:

| Method | Path | Description | Key Parameters |
|:---|:---|:---|:---|
| `GET` | `/api/health` | Service health and DB connectivity check | None |
| `GET` | `/api/analytics/overview` | Executive summary metrics (GMV, orders, unique customers, AOV, repeat rate) | `bypass_cache` |
| `GET` | `/api/analytics/segments` | RFM segment breakdown (customer counts, total revenue, average recency) | `bypass_cache` |
| `GET` | `/api/analytics/rfm` | RFM segment breakdown (convenience alias) | `bypass_cache` |
| `GET` | `/api/analytics/revenue-at-risk` | Projected revenue at risk aggregate and segment exposure | `include_preview`, `bypass_cache` |
| `GET` | `/api/analytics/revenue` | Revenue & GMV time-series trends (monthly, weekly, daily) | `interval`, `start_date`, `end_date`, `bypass_cache` |
| `GET` | `/api/analytics/retention` | Customer cohort retention decay curves ($M+0 \dots M+12$) | `bypass_cache` |
| `GET` | `/api/analytics/cache/stats` | In-memory TTL cache telemetry (hits, misses, hit ratio) | None |
| `POST` | `/api/analytics/cache/clear` | Invalidate and purge all active cache entries | None |
| `GET` | `/api/customers` | Paginated customer list with segment, risk tier, and spend filters | `page`, `page_size`, `segment`, `risk_tier`, `retention_priority`, `state`, `min_spend`, `max_spend`, `search`, `sort_by`, `sort_order` |
| `GET` | `/api/customers/at-risk` | Prioritized list of high-value customers with elevated churn probability | `page`, `page_size`, `risk_tier`, `retention_priority` |
| `GET` | `/api/customers/export` | Streaming CSV export for marketing & retention campaigns | `segment`, `risk_tier`, `retention_priority`, `state`, `min_spend`, `max_spend`, `format` |
| `GET` | `/api/customers/{customer_unique_id}` | Detailed customer intelligence profile and historical orders | `customer_unique_id` |
| `GET` | `/api/customers/{customer_unique_id}/rfm` | RFM scorecard and quintile breakdown for a specific customer | `customer_unique_id` |
| `GET` | `/api/customers/{customer_unique_id}/churn` | Churn risk assessment, model features, and retention action | `customer_unique_id` |
| `GET` | `/api/products` | Paginated product catalog with sales velocity, revenue, and review ratings | `page`, `page_size`, `category`, `sort_by`, `sort_order`, `search`, `bypass_cache` |
| `GET` | `/api/products/categories` | Product category market share, unit sales, and revenue breakdown | `bypass_cache` |
| `GET` | `/api/products/{product_id}` | Product 360 scorecard, package dimensions, and review scores | `product_id`, `bypass_cache` |
| `GET` | `/api/sellers` | Paginated marketplace seller directory with fulfillment and revenue metrics | `page`, `page_size`, `state`, `sort_by`, `sort_order`, `search`, `bypass_cache` |
| `GET` | `/api/sellers/{seller_id}` | Marketplace seller 360 profile, top categories, and delay metrics | `seller_id`, `bypass_cache` |

> [!IMPORTANT]
> All single-customer endpoints use `customer_unique_id` (the true customer identifier), NOT `customer_id` (which is order-scoped in Olist).