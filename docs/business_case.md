# Business Case & Value Proposition

## Executive Summary

Businesses collect vast amounts of transactional data, yet traditional sales records fail to answer critical retention questions:
- Which customers generate the bulk of customer lifetime value?
- Who is drifting toward inactivity or immediate churn?
- How much financial exposure is represented by customers at risk?
- What retention actions should be prioritized given finite marketing and account management bandwidth?

**Mercury** bridges the gap between raw e-commerce transaction logs and executive decision-making. By uniting **RFM segmentation, predictive machine learning, and financial exposure modeling**, Mercury transforms transaction logs into prioritized retention workflows.

---

## The Retention Dilemma in E-Commerce

In large-scale marketplaces like Olist:
1. **Low Repeat Purchase Rate**: Only ~3.1% of customers make more than one purchase historically.
2. **Untargeted Retention Waste**: Treating all customers equally leads to misallocated retention capital (e.g., offering large discounts to low-value or low-intent customers).
3. **Delayed Action**: By the time an executive realizes customer volume has dropped, high-value customers have already defected.

Mercury introduces a **Revenue-at-Risk** framework that combines the probability of churn with monetary value:

$$\text{Expected Revenue at Risk} = P(\text{Churn}) \times \text{Customer Value}$$

---

## Actionable Decision Matrix

| Segment Value | High Churn Risk ($P \ge 0.70$) | Low Churn Risk ($P < 0.30$) |
|:---|:---|:---|
| **High Value (VIP / Champions)** | **Priority 1: Urgent High-Touch Intervention**<br>Direct concierge outreach, tailored incentive, priority resolution. | **Priority 2: Loyalty & Advocacy**<br>VIP perks, early product access, referral programs. |
| **Moderate Value (Potential Loyalists)** | **Priority 3: Re-engagement Campaigns**<br>Targeted marketing automation, discount coupons, cross-sell. | **Priority 4: Organic Growth**<br>Standard product newsletters, seasonal promotions. |
| **Low Value (One-Time / Lost)** | **Priority 5: Low-Cost Automated Triggers**<br>Automated win-back emails; avoid expensive human intervention. | **Priority 6: Baseline Nurture**<br>Standard transactional communications. |

---

## Sustainable Development Goals (SDG) Alignment

Mercury directly supports United Nations Sustainable Development Goals:

- **SDG 8: Decent Work and Economic Growth**:
  Empowers e-commerce merchants and small businesses with enterprise-grade customer intelligence, improving operating margins and sustainable business continuity.
- **SDG 9: Industry, Innovation, and Infrastructure**:
  Showcases modern, scalable data infrastructure—leveraging cloud PostgreSQL, modern ELT transformations with dbt, automated feature engineering, and high-performance REST APIs.
- **SDG 12: Responsible Consumption and Production**:
  Enables sellers to better analyze delivery fulfillment delays, review sentiment, and product returns, reducing logistical waste and improving customer fulfillment accuracy.
