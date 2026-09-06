# Mercury Data Schema

Last updated: 2026-09-06 (Phase 2 — PostgreSQL Schema implemented)

SQL files: `sql/schema.sql` (tables + indexes) · `sql/views.sql` (analytical views)
Migration runner: `sql/migrate.py`

Treat schema changes as contract changes: update this file, `sql/schema.sql`, `sql/views.sql`, and any affected tests together.

---

## Tables

### countries
| Column       | Type         | Notes                                   |
|--------------|--------------|-----------------------------------------|
| country_id   | SERIAL PK    | Surrogate key                           |
| country_name | VARCHAR(100) | UNIQUE. Name as in Online Retail II     |

### products
| Column      | Type        | Notes                                          |
|-------------|-------------|------------------------------------------------|
| stock_code  | VARCHAR(20) | PK. Natural key from dataset (e.g. 85123A)     |
| description | TEXT        | Most recent description; may vary per invoice  |
| created_at  | TIMESTAMPTZ | UTC default NOW()                              |
| updated_at  | TIMESTAMPTZ | Updated by ETL when description changes        |

### customers
| Column        | Type        | Notes                                        |
|---------------|-------------|----------------------------------------------|
| customer_id   | INTEGER PK  | 5-digit CustomerID from Online Retail II      |
| country_id    | INTEGER FK  | → countries. Most frequent country (ETL set) |
| first_order_at | TIMESTAMPTZ | Earliest valid invoice date                 |
| last_order_at  | TIMESTAMPTZ | Most recent valid invoice date (recency base)|
| created_at    | TIMESTAMPTZ | UTC default NOW()                            |
| updated_at    | TIMESTAMPTZ | UTC default NOW()                            |

Indexes: `country_id`, `last_order_at`

### orders
| Column       | Type        | Notes                                          |
|--------------|-------------|------------------------------------------------|
| invoice      | VARCHAR(20) | PK. Natural invoice number (e.g. 536365)       |
| customer_id  | INTEGER FK  | → customers. NOT NULL, CASCADE delete          |
| country_id   | INTEGER FK  | → countries                                    |
| invoice_date | TIMESTAMPTZ | UTC-normalised InvoiceDate. NOT NULL           |
| is_cancelled | BOOLEAN     | TRUE if invoice starts with 'C'. Default FALSE |
| created_at   | TIMESTAMPTZ | UTC default NOW()                              |

Indexes: `customer_id`, `invoice_date`, `(customer_id, invoice_date)`

### order_items
| Column     | Type          | Notes                                           |
|------------|---------------|-------------------------------------------------|
| item_id    | BIGSERIAL PK  | Surrogate key                                   |
| invoice    | VARCHAR(20) FK | → orders. CASCADE delete                       |
| stock_code | VARCHAR(20) FK | → products                                    |
| quantity   | INTEGER       | CHECK ≠ 0. ETL excludes zero-quantity rows      |
| unit_price | NUMERIC(12,4) | CHECK ≥ 0. Zero allowed (gifts/samples)         |
| revenue    | NUMERIC(14,4) | **Generated stored**: quantity × unit_price     |
| created_at | TIMESTAMPTZ   | UTC default NOW()                               |

Indexes: `invoice`, `stock_code`, `(invoice, stock_code)`

### customer_metrics
| Column                  | Type          | Notes                                              |
|-------------------------|---------------|----------------------------------------------------|
| customer_id             | INTEGER PK FK | → customers. CASCADE delete                        |
| recency_days            | INTEGER       | Days since last invoice (relative to ref date)     |
| frequency               | INTEGER       | Distinct valid invoice count                       |
| monetary                | NUMERIC(14,2) | Total spend in GBP                                 |
| rfm_r_score             | SMALLINT      | Recency quintile 1–5 (5 = most recent)             |
| rfm_f_score             | SMALLINT      | Frequency quintile 1–5 (5 = highest)              |
| rfm_m_score             | SMALLINT      | Monetary quintile 1–5 (5 = highest)               |
| rfm_segment             | VARCHAR(50)   | VIP / Loyal / At Risk / Lost / etc.                |
| churn_probability       | NUMERIC(6,5)  | Model output in [0, 1]                             |
| is_churned              | BOOLEAN       | Ground-truth label for model training              |
| revenue_at_risk         | NUMERIC(14,2) | monetary × churn_probability                       |
| avg_order_value         | NUMERIC(12,2) | total_revenue ÷ order_count                        |
| purchase_frequency      | NUMERIC(10,4) | Orders per time unit                               |
| unique_products         | INTEGER       | Count of distinct StockCodes purchased             |
| return_rate             | NUMERIC(6,5)  | Fraction of items returned in [0, 1]               |
| avg_days_between_orders | NUMERIC(10,2) | Mean inter-order gap in days                       |
| total_items             | INTEGER       | Total line items purchased                         |
| last_order_date         | TIMESTAMPTZ   | Denormalised from customers.last_order_at          |
| computed_at             | TIMESTAMPTZ   | First computation timestamp                        |
| updated_at              | TIMESTAMPTZ   | Most recent pipeline refresh                       |

Indexes: `rfm_segment`, `churn_probability DESC`, `revenue_at_risk DESC`, `is_churned`

---

## Analytical Views

| View                        | Purpose                                              |
|-----------------------------|------------------------------------------------------|
| `vw_customer_revenue`       | Per-customer revenue aggregates (RFM + ML input)     |
| `vw_rfm_base`               | Adds recency_days relative to max invoice date       |
| `vw_at_risk_customers`      | Churn-ranked list with priority tier                 |
| `vw_segment_summary`        | Segment-level counts and revenue for BI dashboards   |
| `vw_revenue_at_risk_summary`| Single-row exposure summary for API endpoint         |

---

## Design Rules

- All timestamps are TIMESTAMPTZ (UTC).
- Money uses NUMERIC: NUMERIC(12,4) for unit prices, NUMERIC(14,2) for totals.
- `order_items.revenue` is a generated stored column — do not write to it directly.
- Schema changes require updating this file, `sql/schema.sql`, `sql/views.sql`, and affected tests.
- Never expose raw `DATABASE_URL` or credentials through API responses or logs.