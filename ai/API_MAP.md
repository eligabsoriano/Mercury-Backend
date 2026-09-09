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
| `GET` | `/api/analytics/cache/stats` | In-memory TTL cache telemetry (hits, misses, hit ratio) | None |
| `POST` | `/api/analytics/cache/clear` | Invalidate and purge all active cache entries | None |
| `GET` | `/api/customers` | Paginated customer list with segment, risk tier, and spend filters | `page`, `page_size`, `segment`, `risk_tier`, `retention_priority`, `state`, `min_spend`, `max_spend`, `search`, `sort_by`, `sort_order` |
| `GET` | `/api/customers/{customer_unique_id}` | Detailed customer intelligence profile and historical orders | `customer_unique_id` |
| `GET` | `/api/customers/{customer_unique_id}/rfm` | RFM scorecard and quintile breakdown for a specific customer | `customer_unique_id` |
| `GET` | `/api/customers/{customer_unique_id}/churn` | Churn risk assessment, model features, and retention action | `customer_unique_id` |
| `GET` | `/api/customers/at-risk` | Prioritized list of high-value customers with elevated churn probability | `page`, `page_size`, `risk_tier`, `retention_priority` |
| `GET` | `/api/products` | Category performance, average review scores, and volume | `category`, `limit` |
| `GET` | `/api/sellers` | Seller fulfillment metrics, delay days, and customer rating averages | `seller_id`, `state`, `limit` |

> [!IMPORTANT]
> All single-customer endpoints use `customer_unique_id` (the true customer identifier), NOT `customer_id` (which is order-scoped in Olist).