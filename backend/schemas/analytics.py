"""
backend/schemas/analytics.py
============================
Pydantic schemas for portfolio-level analytics, RFM distribution, and revenue-at-risk summaries.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.churn import RetentionPrioritySummary, RiskTierSummary
from backend.schemas.customer import CustomerSummary
from backend.schemas.rfm import SegmentDistribution


class PortfolioOverview(BaseModel):
    """Macro-level portfolio retention and customer intelligence KPIs."""

    model_config = ConfigDict(from_attributes=True)

    total_customers: int = Field(..., description="Total unique customers in portfolio")
    total_orders: int = Field(..., description="Total completed delivered orders")
    total_revenue: float = Field(..., description="Total historical portfolio revenue in BRL")
    avg_order_value: float = Field(..., description="Portfolio-wide average order value in BRL")
    repeat_buyer_rate: float = Field(
        ..., description="Percentage of repeat customers (lifetime orders >= 2)"
    )
    portfolio_revenue_at_risk: float = Field(
        ..., description="Total expected monetary revenue at risk in BRL"
    )
    portfolio_risk_percentage: float = Field(
        ..., description="Proportion of total revenue currently at risk"
    )
    avg_churn_probability: float = Field(
        ..., description="Portfolio mean customer churn probability"
    )
    high_risk_customers_count: int = Field(..., description="Total customers with P(Churn) >= 0.70")
    high_risk_percentage: float = Field(
        ..., description="Percentage of customers categorized as High Risk"
    )
    vip_retention_revenue_at_risk: float = Field(
        ..., description="Revenue at risk in Priority 1 (VIP Retention)"
    )


class SegmentsOverview(BaseModel):
    """Distribution of customer base across RFM behavioral segments."""

    model_config = ConfigDict(from_attributes=True)

    total_customers: int = Field(..., description="Total customers analyzed")
    segments: List[SegmentDistribution] = Field(
        ..., description="Per-segment customer counts, spend, and averages"
    )


class RevenueAtRiskOverview(BaseModel):
    """Detailed financial breakdown of churn exposure and retention priority groups."""

    model_config = ConfigDict(from_attributes=True)

    total_revenue_at_risk: float = Field(
        ..., description="Total expected monetary revenue at risk in BRL"
    )
    total_historical_spend: float = Field(..., description="Total lifetime historical spend in BRL")
    portfolio_risk_percentage: float = Field(
        ..., description="Revenue at risk as percentage of total revenue"
    )
    by_risk_tier: List[RiskTierSummary] = Field(
        ..., description="Risk distribution across High, Medium, Low"
    )
    by_retention_priority: List[RetentionPrioritySummary] = Field(
        ..., description="Actionable retention priority segments"
    )
    top_at_risk_preview: Optional[List[CustomerSummary]] = Field(
        None, description="Top high-value customers at risk"
    )


class RevenueTrendPoint(BaseModel):
    """Historical time-series revenue and fulfillment data point."""

    model_config = ConfigDict(from_attributes=True)

    period: str = Field(..., description="Time period label (e.g. '2017-01' or '2017-W14')")
    gmv: float = Field(..., description="Gross merchandise value (product + freight) in BRL")
    orders_count: int = Field(..., description="Total orders placed in this period")
    delivered_count: int = Field(..., description="Orders successfully delivered in this period")
    avg_order_value: float = Field(..., description="Average order value in BRL")
    total_freight: float = Field(..., description="Total shipping freight charges in BRL")
    late_order_rate: float = Field(
        ..., description="Percentage of orders delivered past estimated date"
    )


class RevenueAnalyticsResponse(BaseModel):
    """Time-series revenue trends response with summary metadata."""

    model_config = ConfigDict(from_attributes=True)

    interval: str = Field(..., description="Granularity interval: 'month', 'week', or 'day'")
    total_periods: int = Field(..., description="Number of historical time periods returned")
    trends: List[RevenueTrendPoint] = Field(
        ..., description="Ordered chronological trend data points"
    )


class CohortRetentionPoint(BaseModel):
    """Customer cohort retention rates over month-by-month survival lifecycle."""

    model_config = ConfigDict(from_attributes=True)

    cohort_month: str = Field(..., description="Acquisition cohort month in YYYY-MM format")
    cohort_size: int = Field(
        ..., description="Total distinct customers acquired in this cohort month"
    )
    retention_rates: dict[str, float] = Field(
        ...,
        description="Retention survival rates indexed by month offset (e.g. {'m0': 100.0, 'm1': 4.2})",
    )


class RetentionAnalyticsResponse(BaseModel):
    """Comprehensive cohort retention curves across acquisition months."""

    model_config = ConfigDict(from_attributes=True)

    total_cohorts: int = Field(..., description="Total customer acquisition cohorts analyzed")
    cohorts: List[CohortRetentionPoint] = Field(
        ..., description="Cohort retention survival matrices"
    )
