"""
backend/routers/analytics.py
============================
Analytics and business intelligence endpoints for macro portfolio KPIs,
RFM customer segmentation breakdown, and financial revenue-at-risk exposure.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.analytics import (
    PortfolioOverview,
    RevenueAtRiskOverview,
    SegmentsOverview,
)
from backend.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get(
    "/overview",
    response_model=PortfolioOverview,
    summary="Portfolio Macro Overview KPIs",
    description=(
        "Returns high-level customer retention, aggregate spend, "
        "repeat purchase rate, and total revenue-at-risk exposure across the portfolio."
    ),
)
def get_portfolio_overview(db: Session = Depends(get_db)) -> PortfolioOverview:
    return AnalyticsService.get_portfolio_overview(db)


@router.get(
    "/segments",
    response_model=SegmentsOverview,
    summary="RFM Segmentation Breakdown",
    description=(
        "Returns portfolio customer distribution across named RFM segments "
        "(Champions, Loyal Customers, Potential Loyalists, New, At Risk, Lost, Others)."
    ),
)
def get_segments_overview(db: Session = Depends(get_db)) -> SegmentsOverview:
    return AnalyticsService.get_segments_overview(db)


@router.get(
    "/rfm",
    response_model=SegmentsOverview,
    summary="RFM Segmentation Breakdown (Alias)",
    description="Convenience alias returning RFM segment distributions.",
)
def get_rfm_overview(db: Session = Depends(get_db)) -> SegmentsOverview:
    return AnalyticsService.get_segments_overview(db)


@router.get(
    "/revenue-at-risk",
    response_model=RevenueAtRiskOverview,
    summary="Revenue-at-Risk & Retention Action Matrix",
    description=(
        "Detailed financial breakdown of churn exposure grouped by risk tier "
        "and prioritized retention action groups, including a top at-risk customer preview."
    ),
)
def get_revenue_at_risk_overview(
    include_preview: bool = True,
    db: Session = Depends(get_db),
) -> RevenueAtRiskOverview:
    return AnalyticsService.get_revenue_at_risk_overview(
        db, include_top_preview=include_preview
    )
