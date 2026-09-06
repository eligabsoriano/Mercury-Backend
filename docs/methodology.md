# Analytics and ML Methodology

## Dataset

Mercury uses the Online Retail II dataset from the UCI Machine Learning Repository. Relevant fields include:

- `Invoice`: transaction identifier
- `StockCode`: product identifier
- `Description`: product description
- `Quantity`: units purchased
- `InvoiceDate`: transaction date and time
- `UnitPrice`: price per unit
- `CustomerID`: customer identifier
- `Country`: customer country

The dataset includes cancellations and returns, which must be handled during preparation.

## Data Preparation

The ETL process should:

- Inspect structure, missing values, duplicates, and anomalies
- Handle missing customer identifiers
- Identify cancelled invoices and returns
- Convert transaction dates to a consistent type
- Calculate transaction revenue as `Quantity * UnitPrice`
- Standardize categorical fields
- Store clean data for analytical queries

## RFM Segmentation

RFM analysis evaluates each customer using:

- **Recency:** time since the last purchase
- **Frequency:** number of purchases or orders
- **Monetary:** total customer spend

Segments can include VIP, Loyal, Potential Loyalist, New Customer, At Risk, and Lost. Segment thresholds should be defined from the prepared dataset and documented with the analysis results.

## Churn Prediction

Potential model features include:

- Days since last purchase
- Total orders
- Total spend
- Average order value
- Purchase frequency
- Unique products purchased
- Return rate
- Average days between orders

Candidate models include Logistic Regression, Random Forest, and Gradient Boosting. Evaluation should include accuracy, precision, recall, F1 score, and ROC-AUC. Precision and recall are especially important because retention resources are limited.

## Revenue at Risk

Revenue at risk combines customer value with churn probability. High-value customers with high churn probability receive the highest retention priority, rather than treating every inactive customer equally.

## Reporting

Power BI should cover:

- Revenue, customers, orders, and average order value
- Repeat customer rate
- Customer count and revenue by RFM segment
- Churn probability and high-risk customer counts
- High-value customers at risk
- Revenue at risk
- Geographic and product performance

The React interface can provide customer-level details such as segment, churn risk, historical spend, order count, risk factors, and recommended action.
