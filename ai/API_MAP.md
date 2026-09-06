# Mercury API Map

Last updated: 2026-09-06 (FastAPI Surface for Olist Dataset)

The planned FastAPI REST endpoints connect web and mobile clients to PostgreSQL/dbt marts and ML predictions:

| Method | Path | Description | Key Parameters |
|:---|:---|:---|:---|
| `GET` | `/api/health` | Service health and DB connectivity check | None |
| `GET` | `/api/analytics/overview` | Executive summary metrics (GMV, orders, unique customers, AOV, repeat rate) | `start_date`, `end_date` |
| `GET` | `/api/analytics/segments` | RFM segment breakdown (customer counts, total revenue, average recency) | None |
| `GET` | `/api/analytics/revenue-at-risk` | Projected revenue at risk aggregate and segment exposure | None |
| `GET` | `/api/customers` | Paginated customer list with segment, risk tier, and spend filters | `page`, `page_size`, `segment`, `churn_risk_tier`, `min_spend` |
| `GET` | `/api/customers/{customer_unique_id}` | Detailed customer intelligence profile and historical orders | `customer_unique_id` |
| `GET` | `/api/customers/{customer_unique_id}/rfm` | RFM scorecard and quintile breakdown for a specific customer | `customer_unique_id` |
| `GET` | `/api/customers/{customer_unique_id}/churn` | Churn risk assessment, model features, and retention action | `customer_unique_id` |
| `GET` | `/api/customers/at-risk` | Prioritized list of high-value customers with elevated churn probability | `min_risk_prob`, `limit` |
| `GET` | `/api/products` | Category performance, average review scores, and volume | `category`, `limit` |
| `GET` | `/api/sellers` | Seller fulfillment metrics, delay days, and customer rating averages | `seller_id`, `state`, `limit` |

> [!IMPORTANT]
> All single-customer endpoints use `customer_unique_id` (the true customer identifier), NOT `customer_id` (which is order-scoped in Olist).