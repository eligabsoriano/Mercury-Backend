"""
backend/routers/analytics.py
============================
Analytics and business intelligence endpoints for macro portfolio KPIs,
RFM customer segmentation breakdown, and financial revenue-at-risk exposure.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.analytics import (
    PortfolioOverview,
    RetentionAnalyticsResponse,
    RevenueAnalyticsResponse,
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
def get_portfolio_overview(
    bypass_cache: bool = Query(False, description="Bypass in-memory cache and force live database query"),
    db: Session = Depends(get_db),
) -> PortfolioOverview:
    return AnalyticsService.get_portfolio_overview(db, bypass_cache=bypass_cache)


@router.get(
    "/segments",
    response_model=SegmentsOverview,
    summary="RFM Segmentation Breakdown",
    description=(
        "Returns portfolio customer distribution across named RFM segments "
        "(Champions, Loyal Customers, Potential Loyalists, New, At Risk, Lost, Others)."
    ),
)
def get_segments_overview(
    bypass_cache: bool = Query(False, description="Bypass in-memory cache and force live database query"),
    db: Session = Depends(get_db),
) -> SegmentsOverview:
    return AnalyticsService.get_segments_overview(db, bypass_cache=bypass_cache)


@router.get(
    "/rfm",
    response_model=SegmentsOverview,
    summary="RFM Segmentation Breakdown (Alias)",
    description="Convenience alias returning RFM segment distributions.",
)
def get_rfm_overview(
    bypass_cache: bool = Query(False, description="Bypass in-memory cache and force live database query"),
    db: Session = Depends(get_db),
) -> SegmentsOverview:
    return AnalyticsService.get_segments_overview(db, bypass_cache=bypass_cache)


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
    include_preview: bool = Query(True, description="Include top 5 at-risk customer preview"),
    bypass_cache: bool = Query(False, description="Bypass in-memory cache and force live database query"),
    db: Session = Depends(get_db),
) -> RevenueAtRiskOverview:
    return AnalyticsService.get_revenue_at_risk_overview(
        db, include_top_preview=include_preview, bypass_cache=bypass_cache
    )


@router.get(
    "/revenue",
    response_model=RevenueAnalyticsResponse,
    summary="Revenue Trends Time-Series",
    description=(
        "Returns chronological gross merchandise value (GMV), order volume, AOV, "
        "freight expenses, and late delivery rate time-series trends grouped by interval."
    ),
)
def get_revenue_trends(
    interval: str = Query("month", description="Grouping interval: month, week, or day"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    bypass_cache: bool = Query(False, description="Bypass in-memory cache and force live database query"),
    db: Session = Depends(get_db),
) -> RevenueAnalyticsResponse:
    return AnalyticsService.get_revenue_trends(
        db=db,
        interval=interval,
        start_date=start_date,
        end_date=end_date,
        bypass_cache=bypass_cache,
    )


@router.get(
    "/retention",
    response_model=RetentionAnalyticsResponse,
    summary="Customer Cohort Retention Analysis",
    description=(
        "Returns month-by-month customer cohort survival rates (M+0 to M+12) "
        "tracking customer retention decay curves based on first purchase acquisition cohorts."
    ),
)
def get_cohort_retention(
    bypass_cache: bool = Query(False, description="Bypass in-memory cache and force live database query"),
    db: Session = Depends(get_db),
) -> RetentionAnalyticsResponse:
    return AnalyticsService.get_cohort_retention(db=db, bypass_cache=bypass_cache)



@router.get(
    "/cache/stats",
    summary="Analytics Cache Telemetry",
    description="Returns real-time in-memory TTL cache telemetry: hits, misses, bypasses, evictions, and hit ratio.",
)
def get_cache_telemetry() -> Dict[str, Any]:
    return AnalyticsService.get_cache_stats()


@router.post(
    "/cache/clear",
    summary="Flush Analytics Cache",
    description="Invalidates and purges all active items from the in-memory analytics cache.",
)
def purge_analytics_cache() -> Dict[str, Any]:
    cleared = AnalyticsService.clear_cache()
    return {"status": "cleared", "items_removed": cleared}
