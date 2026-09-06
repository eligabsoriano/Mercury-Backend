# Analytics and Machine Learning Methodology

## 1. Datasets

### Primary Dataset: Olist Brazilian E-Commerce
Mercury uses the **Olist Brazilian E-Commerce Public Dataset** (approx. 100,000 orders from 2016 to 2018) as its primary transactional foundation. The data is structured across multiple relational entities:

- `orders`: Order lifecycle states, purchase timestamps, estimated and actual delivery dates.
- `customers`: Key mapping entity containing both `customer_id` (order-scoped foreign key) and `customer_unique_id` (true returning customer identifier), along with location data.
- `order_items`: Line-item pricing, freight fees, product identifiers, and seller identifiers.
- `order_payments`: Payment methods (credit card, boleto, voucher, debit), installments, and payment values.
- `order_reviews`: Customer satisfaction ratings (1 to 5 stars), timestamps, and review comments.
- `products`: Category classifications, product dimensions, and weights.
- `sellers`: Seller identifiers and geographic locations.
- `category_translations`: English mappings for Portuguese product categories.
- `geolocation`: Brazilian zip prefix coordinates and locations.

### Supporting Module: Olist Marketing Funnel (Optional)
The **Olist Marketing Funnel** dataset provides seller acquisition and conversion details:
- `mql`: Marketing qualified leads, channels/origins (organic, paid search, social), and contact dates.
- `closed_deals`: Converted sellers, deal close dates, business segments, and declared revenue.

> **Scope Isolation**: Because the marketing funnel is seller-oriented (joining on `seller_id`), it is maintained in a distinct `raw_marketing` schema and does not compromise customer transaction integrity.

---

## 2. Critical Data Identity: customer_id vs customer_unique_id

In the Olist dataset:
- `customer_id`: Assigned per order. A customer who orders three times receives three distinct `customer_id` values.
- `customer_unique_id`: Identifies the real individual across repeated transactions.

> [!IMPORTANT]
> All customer analytics, RFM segmentation, lifetime spend, churn modeling, and retention recommendations **must aggregate on `customer_unique_id`**. Joining orders directly by `customer_id` without resolving `customer_unique_id` results in treating 100% of transactions as one-off customers.

---

## 3. Data Preparation and Transformation (ELT with dbt)

Mercury utilizes an ELT pattern with PostgreSQL and dbt:

1. **Ingestion**: Raw CSV data is copied as-is into `raw.*` and `raw_marketing.*` tables.
2. **Staging (`staging.*`)**:
   - Filter `stg_orders` to `delivered` status for realized revenue calculations.
   - Clean timestamps and calculate delivery performance metrics:
     $$\text{delivery\_delay\_days} = \text{order\_delivered\_customer\_date} - \text{order\_estimated\_delivery\_date}$$
     *(positive = late delivery, negative = delivered ahead of estimate)*.
   - Calculate item-level total revenue: $\text{item\_revenue} = \text{price} + \text{freight\_value}$.
   - Aggregate payments to order level with flags for multiple payment methods and primary payment type.
   - Flag review sentiment: `is_negative_review` (score $\le$ 2), `is_positive_review` (score $\ge$ 4).
   - Resolve English category names and normalize geographic strings.
3. **Intermediate & Marts (`intermediate.*`, `mart.*`)**:
   - Aggregate all transaction, payment, review, and fulfillment dimensions by `customer_unique_id`.

---

## 4. RFM Customer Segmentation

### Dimensions
- **Recency ($R$)**: Number of days from the customer's most recent delivered order purchase date to the observation cutoff date.
- **Frequency ($F$)**: Count of distinct delivered orders placed by `customer_unique_id`.
- **Monetary ($M$)**: Total spend (price + freight) across all delivered orders.

### Distribution Challenge in E-Commerce
In the Olist dataset, approximately **96.9%** of customers have only 1 order, and **3.1%** have 2 or more orders. Standard quintile binning on Frequency produces degenerate splits. Therefore:
- Frequency is segmented using behavioral splits (e.g., $F=1$ vs $F \ge 2$, with sub-tiering on multi-item orders).
- Recency and Monetary metrics are scored into quintiles (1–5) or quartile-based scorecards.

### Segment Definitions
- **Champions**: Highest spenders with recent purchases ($R=4\text{--}5$, $M=4\text{--}5$).
- **Loyal Customers**: Multiple purchases ($F \ge 2$) with steady recency and solid monetary value.
- **Potential Loyalists**: Recent buyers ($R=4\text{--}5$) with above-average single-order spend.
- **New Customers**: Recent buyers ($R=4\text{--}5$) with moderate/low initial purchase value.
- **At Risk**: High historical spenders whose recency has lapsed ($R \le 2$, $M=4\text{--}5$).
- **Lost / Inactive**: Low recency, low engagement, and low repeat rate ($R \le 2$, $M \le 2$).

---

## 5. Churn Prediction

### Churn Label Definition
Because the repeat-purchase rate is low overall, defining churn simply as "never ordered again" labels 97% of the dataset as churned immediately. Instead, Mercury employs a **time-bounded observation window**:
- Let $T_{\text{obs}}$ be the observation snapshot date.
- A customer is defined as active if they completed a transaction within the last $W$ days (e.g., 90 or 180 days).
- A customer is defined as **churned** if their inactivity exceeds $W$ days without returning.

### Feature Engineering
Features extracted per `customer_unique_id` prior to the observation window cutoff:
- **RFM Features**: Days since last order, total completed orders, total lifetime spend, average order value (AOV).
- **Fulfillment / Friction Features**:
  - Maximum and average delivery delay days.
  - Count and proportion of orders delivered late.
  - Average freight-to-price ratio.
- **Satisfaction Features**:
  - Average review score.
  - Presence of negative reviews ($\le 2$ stars).
  - Count of review comments submitted.
- **Order Characteristics**:
  - Average items per order.
  - Number of distinct product categories purchased.
  - Average payment installments used.

### Candidate Algorithms and Evaluation
- **Models**: Logistic Regression (baseline), Random Forest Classifier, Gradient Boosting (LightGBM/XGBoost).
- **Validation**: Time-based train/test split to prevent temporal leakage (train on earlier cohort, validate on later cohort).
- **Metrics**:
  - ROC-AUC: Overall ranking capability across risk tiers.
  - Precision @ Top $K$: Critical because retention intervention capacity (discounts, outreach) is resource-constrained.
  - F1-Score and Recall: To identify high-loss at-risk pools.

---

## 6. Revenue-at-Risk Analysis

Mercury couples churn probability with customer monetary value to prioritize retention actions by financial impact:

$$\text{Expected Revenue at Risk} = P(\text{Churn}) \times \text{Customer Value}$$

Where $\text{Customer Value}$ is derived from annualized historical spend or Average Order Value (AOV).

### Priority Decision Matrix

| Segment Value | High Churn Risk ($P > 0.7$) | Low Churn Risk ($P < 0.3$) |
|:---|:---|:---|
| **High Monetary** | **Priority 1: Immediate VIP Retention**<br>High-touch proactive outreach, exclusive compensation, concierge service. | **Priority 2: Loyalty & Nurture**<br>VIP rewards, early product access, brand advocacy programs. |
| **Low Monetary** | **Priority 3: Automated Re-engagement**<br>Automated low-cost email sequence or coupon trigger. | **Priority 4: Standard Operations**<br>Organic marketing and standard promotions. |

---

## 7. Business Intelligence & Decision Support

The analytical outputs are exposed through:
1. **Power BI Reporting**:
   - Executive overview: GMV, order volume, average order value, overall repeat rate.
   - Customer intelligence: RFM segment breakdown, churn risk distribution, total revenue at risk.
   - Operational factors: Late delivery correlation with review scores and subsequent customer churn.
2. **FastAPI Services**:
   - Programmatic access for web and mobile clients to query customer segments, individual customer risk scorecards, and prioritized retention lists.
