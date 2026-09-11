# Business Intelligence & Reporting Specifications

Mercury feeds insights to decision-makers through **Power BI dashboards** and dedicated client interfaces (**Web** and **Mobile**).

---

## 1. Power BI Dashboards

> [!NOTE]
> For exact connection strings, Neon PostgreSQL DirectQuery configuration, star-schema table relationships, and DAX measure formulas, see the dedicated [Power BI Setup Guide](powerbi_setup.md).

### Executive Overview Dashboard
- **Total Revenue & Gross Merchandise Value (GMV)**: Historical and period-to-date tracking via `Total GMV = SUM(fact_orders[total_amount])`.
- **Order Volume & Average Order Value (AOV)**: Transaction velocity and basket size analysis via `Average Order Value = DIVIDE([Total GMV], [Total Orders], 0)`.
- **Customer Acquisition vs Repeat Rate**: Tracking customer retention health via `Repeat Purchase Rate`.
- **Aggregate Revenue at Risk**: Total projected financial exposure across inactive segments via `Portfolio Revenue at Risk = SUM(churn_predictions[revenue_at_risk])`.
- **Customer Satisfaction Indicator**: Aggregate review rating (1–5) and trendline via `Average Review Rating = AVERAGE(fact_orders[review_score])`.

### Customer Intelligence & Retention Dashboard
- **RFM Segment Matrix**: Visual grid distribution of customers across Champions, Loyal, Potential Loyalists, At Risk, and Lost segments.
- **Churn Probability Distribution**: Histogram and risk tiers (Low, Medium, High).
- **At-Risk VIP List**: Drill-down table listing high-value customers with elevated churn probability (`VIP Revenue at Risk`).
- **Customer Value vs Churn Probability Scatter**: Visualizing retention priorities.

### Operational & Seller Performance Dashboard
- **Delivery Reliability**: Carrier transit time, actual delivery vs estimated delivery date, late delivery percentage (`Late Delivery Rate`).
- **Review Sentiment Impact**: Correlation between delivery delays and 1–2 star review scores (`Negative Review Share`).
- **Seller Performance**: Top revenue-generating sellers, fulfillment efficiency, and customer rating distributions.

---

## 2. Client Interfaces

Client applications consume typed contracts synchronized from the backend OpenAPI specification:
- **OpenAPI 3.1 Spec**: [openapi.json](../openapi.json)
- **TypeScript Interface Definitions**: [types/api.ts](../types/api.ts) (2,502 lines generated via `npm run codegen`)

### Web Application (React & TypeScript)
- **Executive Overview**: High-level KPIs, revenue curves, and high-risk alerts.
- **Customer Intelligence Directory**: Searchable, filterable directory by segment, churn tier, and spend.
- **Customer Deep-Dive**: Profile cards showing order timeline, RFM quintiles, review history, and recommended retention action.
- **Action Workspace**: Exportable priority retention lists for CRM and marketing integrations (`GET /api/customers/export`).

### Mobile Application (Flutter & Dart)
- **Decision-Support on the Go**: Lightweight KPI cards and executive alerts.
- **High-Risk Alerts**: Instant notifications for newly flagged at-risk VIP customers.
- **Fast Search**: On-demand lookup of key customer metrics and risk scores (`GET /api/customers/at-risk`).
