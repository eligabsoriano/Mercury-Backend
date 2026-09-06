# Architecture and Implementation

## System Flow

```text
Online Retail II dataset
        |
        v
Python ETL and data cleaning
        |
        v
Neon PostgreSQL
        |
        +--> SQL analytics and customer metrics
        |
        +--> ML feature engineering and churn prediction
        |
        v
Customer intelligence and recommendations
        |
        +--> Power BI dashboard
        +--> FastAPI
                    |
                    v
              React web app
```

## Data Model

The analytical model is organized around these entities:

- `customers`: customer identifiers and profile attributes
- `orders`: invoice-level transactions
- `order_items`: products, quantities, and prices per order
- `products`: product metadata
- `countries`: country reference data
- `customer_metrics`: aggregated customer behavior and model outputs

SQL views can expose clean analytical datasets for Power BI and machine-learning workflows.

## Data and ML Workflow

1. Collect and inspect the Online Retail II dataset.
2. Clean transactions and calculate revenue.
3. Load the prepared data into PostgreSQL.
4. Calculate customer metrics and RFM segments.
5. Engineer features for churn prediction.
6. Train and evaluate classification models.
7. Calculate revenue at risk and retention priority.
8. Publish results through Power BI, FastAPI, and React.

## API Surface

The planned FastAPI endpoints are:

```text
GET /customers
GET /customers/{customer_id}
GET /customers/{customer_id}/rfm
GET /customers/{customer_id}/churn
GET /customers/at-risk
GET /customers/revenue-at-risk
```

## Suggested Project Structure

```text
mercury/
├── data/
│   ├── raw/
│   └── processed/
├── notebooks/
├── etl/
├── sql/
├── ml/
├── backend/
├── frontend/
├── powerbi/
├── docs/
├── requirements.txt
└── README.md
```
