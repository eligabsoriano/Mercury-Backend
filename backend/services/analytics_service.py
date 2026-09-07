"""
backend/services/analytics_service.py
=====================================
Database queries and aggregations for portfolio-level analytics,
RFM segment breakdown, and revenue-at-risk exposure.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.schemas.analytics import (
    PortfolioOverview,
    RevenueAtRiskOverview,
    SegmentsOverview,
)
from backend.schemas.churn import (
    RetentionPrioritySummary,
    RiskTierSummary,
)
from backend.schemas.customer import CustomerSummary
from backend.schemas.rfm import SegmentDistribution

log = logging.getLogger(__name__)


class AnalyticsService:
    """Service providing aggregate customer portfolio analytics and financial metrics."""

    @staticmethod
    def get_portfolio_overview(db: Session) -> PortfolioOverview:
        """
        Aggregate macro-level portfolio KPIs: total customers, revenue, AOV,
        repeat rate, total revenue-at-risk, and VIP retention exposure.
        """
        # 1. Customer metrics aggregation
        cust_query = text(
            """
            SELECT
                COUNT(*) AS total_customers,
                COALESCE(SUM(lifetime_orders), 0) AS total_orders,
                COALESCE(SUM(lifetime_spend), 0.0) AS total_revenue,
                COALESCE(AVG(avg_order_value), 0.0) AS avg_order_value,
                COALESCE(AVG(CASE WHEN is_repeat_buyer THEN 1.0 ELSE 0.0 END), 0.0) * 100.0 AS repeat_buyer_rate
            FROM mart.mart_customer_metrics
            """
        )
        cust_row = db.execute(cust_query).mappings().one()

        # 2. Churn & Revenue-at-Risk aggregation
        churn_query = text(
            """
            SELECT
                COALESCE(SUM(revenue_at_risk), 0.0) AS portfolio_revenue_at_risk,
                COALESCE(AVG(churn_probability), 0.0) AS avg_churn_probability,
                COUNT(*) FILTER (WHERE risk_tier = 'High') AS high_risk_customers_count,
                COALESCE(
                    SUM(revenue_at_risk) FILTER (WHERE retention_priority = 'Priority 1: Immediate VIP Retention'),
                    0.0
                ) AS vip_retention_revenue_at_risk
            FROM ml.churn_predictions
            """
        )
        churn_row = db.execute(churn_query).mappings().one()

        total_customers = int(cust_row["total_customers"])
        total_revenue = round(float(cust_row["total_revenue"]), 2)
        portfolio_rar = round(float(churn_row["portfolio_revenue_at_risk"]), 2)
        high_risk_count = int(churn_row["high_risk_customers_count"])

        risk_percentage = (
            round((portfolio_rar / total_revenue) * 100.0, 2)
            if total_revenue > 0
            else 0.0
        )
        high_risk_pct = (
            round((high_risk_count / total_customers) * 100.0, 2)
            if total_customers > 0
            else 0.0
        )

        return PortfolioOverview(
            total_customers=total_customers,
            total_orders=int(cust_row["total_orders"]),
            total_revenue=total_revenue,
            avg_order_value=round(float(cust_row["avg_order_value"]), 2),
            repeat_buyer_rate=round(float(cust_row["repeat_buyer_rate"]), 2),
            portfolio_revenue_at_risk=portfolio_rar,
            portfolio_risk_percentage=risk_percentage,
            avg_churn_probability=round(float(churn_row["avg_churn_probability"]), 4),
            high_risk_customers_count=high_risk_count,
            high_risk_percentage=high_risk_pct,
            vip_retention_revenue_at_risk=round(
                float(churn_row["vip_retention_revenue_at_risk"]), 2
            ),
        )

    @staticmethod
    def get_segments_overview(db: Session) -> SegmentsOverview:
        """
        Aggregate portfolio distribution across RFM customer segments.
        Calculates customer counts, percentage, total spend, and averages.
        """
        total_customers_query = text("SELECT COUNT(*) FROM ml.rfm_segments")
        total_customers = db.execute(total_customers_query).scalar() or 0

        query = text(
            """
            SELECT
                segment,
                COUNT(*) AS customer_count,
                COALESCE(SUM(monetary), 0.0) AS total_spend,
                COALESCE(AVG(monetary), 0.0) AS avg_spend,
                COALESCE(AVG(recency_days), 0.0) AS avg_recency_days,
                COALESCE(AVG(frequency), 0.0) AS avg_frequency
            FROM ml.rfm_segments
            GROUP BY segment
            ORDER BY total_spend DESC
            """
        )
        rows = db.execute(query).mappings().all()

        segments: List[SegmentDistribution] = []
        for r in rows:
            count = int(r["customer_count"])
            pct = round((count / total_customers) * 100.0, 2) if total_customers > 0 else 0.0
            segments.append(
                SegmentDistribution(
                    segment=r["segment"],
                    customer_count=count,
                    percentage=pct,
                    total_spend=round(float(r["total_spend"]), 2),
                    avg_spend=round(float(r["avg_spend"]), 2),
                    avg_recency_days=round(float(r["avg_recency_days"]), 1),
                    avg_frequency=round(float(r["avg_frequency"]), 2),
                )
            )

        return SegmentsOverview(
            total_customers=total_customers,
            segments=segments,
        )

    @staticmethod
    def get_revenue_at_risk_overview(
        db: Session, include_top_preview: bool = True
    ) -> RevenueAtRiskOverview:
        """
        Detailed financial breakdown of churn exposure across risk tiers and retention priority groups.
        Optionally includes a preview of top high-value customers currently at risk.
        """
        # Overall spend and risk
        summary_query = text(
            """
            SELECT
                COALESCE(SUM(monetary_value), 0.0) AS total_spend,
                COALESCE(SUM(revenue_at_risk), 0.0) AS total_rar,
                COUNT(*) AS total_count
            FROM ml.churn_predictions
            """
        )
        summary_row = db.execute(summary_query).mappings().one()
        total_spend = round(float(summary_row["total_spend"]), 2)
        total_rar = round(float(summary_row["total_rar"]), 2)
        total_count = int(summary_row["total_count"])

        risk_pct = round((total_rar / total_spend) * 100.0, 2) if total_spend > 0 else 0.0

        # By Risk Tier (High, Medium, Low)
        tier_query = text(
            """
            SELECT
                risk_tier,
                COUNT(*) AS customer_count,
                COALESCE(SUM(revenue_at_risk), 0.0) AS total_rar,
                COALESCE(AVG(churn_probability), 0.0) AS avg_prob
            FROM ml.churn_predictions
            GROUP BY risk_tier
            ORDER BY
                CASE risk_tier
                    WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2
                    WHEN 'Low' THEN 3
                    ELSE 4
                END
            """
        )
        tier_rows = db.execute(tier_query).mappings().all()
        by_risk_tier: List[RiskTierSummary] = []
        for r in tier_rows:
            count = int(r["customer_count"])
            pct = round((count / total_count) * 100.0, 2) if total_count > 0 else 0.0
            by_risk_tier.append(
                RiskTierSummary(
                    risk_tier=r["risk_tier"],
                    customer_count=count,
                    percentage=pct,
                    total_revenue_at_risk=round(float(r["total_rar"]), 2),
                    avg_churn_probability=round(float(r["avg_prob"]), 4),
                )
            )

        # By Retention Priority
        priority_query = text(
            """
            SELECT
                retention_priority,
                COUNT(*) AS customer_count,
                COALESCE(SUM(revenue_at_risk), 0.0) AS total_rar
            FROM ml.churn_predictions
            GROUP BY retention_priority
            ORDER BY total_rar DESC
            """
        )
        prio_rows = db.execute(priority_query).mappings().all()
        by_priority: List[RetentionPrioritySummary] = []
        for r in prio_rows:
            count = int(r["customer_count"])
            pct = round((count / total_count) * 100.0, 2) if total_count > 0 else 0.0
            by_priority.append(
                RetentionPrioritySummary(
                    retention_priority=r["retention_priority"],
                    customer_count=count,
                    percentage=pct,
                    total_revenue_at_risk=round(float(r["total_rar"]), 2),
                )
            )

        # Top 5 at-risk customer preview
        top_preview: Optional[List[CustomerSummary]] = None
        if include_top_preview:
            top_query = text(
                """
                SELECT
                    c.customer_unique_id,
                    c.city,
                    c.state,
                    c.zip_prefix,
                    c.first_purchased_at,
                    c.latest_purchased_at,
                    c.recency_days,
                    c.customer_lifespan_days,
                    c.lifetime_orders,
                    c.is_repeat_buyer,
                    c.lifetime_spend,
                    c.avg_order_value,
                    r.segment,
                    ch.churn_probability,
                    ch.risk_tier,
                    ch.revenue_at_risk,
                    ch.retention_priority
                FROM ml.churn_predictions ch
                JOIN mart.mart_customer_metrics c ON ch.customer_unique_id = c.customer_unique_id
                LEFT JOIN ml.rfm_segments r ON ch.customer_unique_id = r.customer_unique_id
                WHERE ch.risk_tier = 'High'
                ORDER BY ch.revenue_at_risk DESC
                LIMIT 5
                """
            )
            top_rows = db.execute(top_query).mappings().all()
            top_preview = [
                CustomerSummary(
                    customer_unique_id=row["customer_unique_id"],
                    city=row["city"],
                    state=row["state"],
                    zip_prefix=row["zip_prefix"],
                    first_purchased_at=row["first_purchased_at"],
                    latest_purchased_at=row["latest_purchased_at"],
                    recency_days=float(row["recency_days"]) if row["recency_days"] is not None else None,
                    customer_lifespan_days=float(row["customer_lifespan_days"]) if row["customer_lifespan_days"] is not None else None,
                    lifetime_orders=int(row["lifetime_orders"]),
                    is_repeat_buyer=int(row["is_repeat_buyer"]),
                    lifetime_spend=round(float(row["lifetime_spend"]), 2),
                    avg_order_value=round(float(row["avg_order_value"]), 2),
                    segment=row["segment"],
                    churn_probability=float(row["churn_probability"]) if row["churn_probability"] is not None else None,
                    risk_tier=row["risk_tier"],
                    revenue_at_risk=float(row["revenue_at_risk"]) if row["revenue_at_risk"] is not None else None,
                    retention_priority=row["retention_priority"],
                )
                for row in top_rows
            ]

        return RevenueAtRiskOverview(
            total_revenue_at_risk=total_rar,
            total_historical_spend=total_spend,
            portfolio_risk_percentage=risk_pct,
            by_risk_tier=by_risk_tier,
            by_retention_priority=by_priority,
            top_at_risk_preview=top_preview,
        )
