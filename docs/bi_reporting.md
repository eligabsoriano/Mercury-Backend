# Business Intelligence & Reporting Specifications

Mercury feeds insights to decision-makers through **Power BI dashboards** and dedicated client interfaces (**Web** and **Mobile**).

---

## 1. Power BI Dashboards

### Executive Overview Dashboard
- **Total Revenue & Gross Merchandise Value (GMV)**: Historical and period-to-date tracking.
- **Order Volume & Average Order Value (AOV)**: Transaction velocity and basket size analysis.
- **Customer Acquisition vs Repeat Rate**: Tracking customer retention health.
- **Aggregate Revenue at Risk**: Total projected financial exposure across inactive segments.
- **Customer Satisfaction Indicator**: Aggregate review rating (1–5) and trendline.

### Customer Intelligence & Retention Dashboard
- **RFM Segment Matrix**: Visual grid distribution of customers across Champions, Loyal, Potential Loyalists, At Risk, and Lost segments.
- **Churn Probability Distribution**: Histogram and risk tiers (Low, Medium, High).
- **At-Risk VIP List**: Drill-down table listing high-value customers with elevated churn probability.
- **Customer Value vs Churn Probability Scatter**: Visualizing retention priorities.

### Operational & Seller Performance Dashboard
- **Delivery Reliability**: Carrier transit time, actual delivery vs estimated delivery date, late delivery percentage.
- **Review Sentiment Impact**: Correlation between delivery delays and 1–2 star review scores.
- **Seller Performance**: Top revenue-generating sellers, fulfillment efficiency, and customer rating distributions.

---

## 2. Client Interfaces

### Web Application (React & TypeScript)
- **Executive Overview**: High-level KPIs, revenue curves, and high-risk alerts.
- **Customer Intelligence Directory**: Searchable, filterable directory by segment, churn tier, and spend.
- **Customer Deep-Dive**: Profile cards showing order timeline, RFM quintiles, review history, and recommended retention action.
- **Action Workspace**: Exportable priority retention lists for CRM and marketing integrations.

### Mobile Application (Flutter & Dart)
- **Decision-Support on the Go**: Lightweight KPI cards and executive alerts.
- **High-Risk Alerts**: Instant notifications for newly flagged at-risk VIP customers.
- **Fast Search**: On-demand lookup of key customer metrics and risk scores.
