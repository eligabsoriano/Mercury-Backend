"""
backend/routers/marketing.py
============================
REST API endpoints for Phase 10: Two-Sided Marketplace Marketing Funnel,
Seller Acquisition Velocity, and Origin Channel Attribution.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.marketing import (
    ChannelAttributionResponse,
    MarketingFunnelOverview,
    MarketingLeadsListResponse,
    SalesVelocityMetrics,
    SegmentPerformanceResponse,
)
from backend.services.marketing_service import MarketingService

router = APIRouter(prefix="/api/marketing", tags=["Marketing"])


@router.get(
    "/overview",
    response_model=MarketingFunnelOverview,
    summary="Marketing Funnel Overview",
    description=(
        "Retrieve high-level seller acquisition marketing funnel performance KPIs, "
        "including total MQL volume, closed deals won, overall conversion rate, sales velocity, "
        "declared seller revenue, and realized marketplace GMV."
    ),
)
def get_funnel_overview(
    bypass_cache: bool = Query(
        False, description="Bypass in-memory cache and re-query the database"
    ),
    db: Session = Depends(get_db),
) -> MarketingFunnelOverview:
    return MarketingService.get_funnel_overview(db, bypass_cache=bypass_cache)


@router.get(
    "/channels",
    response_model=ChannelAttributionResponse,
    summary="Origin Channel Attribution",
    description=(
        "Retrieve marketing qualified lead volume, conversion rates, sales cycle duration, "
        "and revenue contribution broken down by lead acquisition channel (Organic, Paid Search, Social, etc.)."
    ),
)
def get_channel_attribution(
    bypass_cache: bool = Query(
        False, description="Bypass in-memory cache and re-query the database"
    ),
    db: Session = Depends(get_db),
) -> ChannelAttributionResponse:
    return MarketingService.get_channel_attribution(db, bypass_cache=bypass_cache)


@router.get(
    "/velocity",
    response_model=SalesVelocityMetrics,
    summary="Seller Acquisition Sales Velocity",
    description=(
        "Analyze sales cycle duration (days elapsed from initial MQL contact to won closed deal) "
        "across business segments and lead types, highlighting the fastest and slowest segments."
    ),
)
def get_sales_velocity(
    bypass_cache: bool = Query(
        False, description="Bypass in-memory cache and re-query the database"
    ),
    db: Session = Depends(get_db),
) -> SalesVelocityMetrics:
    return MarketingService.get_sales_velocity(db, bypass_cache=bypass_cache)


@router.get(
    "/segments",
    response_model=SegmentPerformanceResponse,
    summary="Business Segment Economic Performance",
    description=(
        "Examine marketplace seller performance by business category segment, comparing "
        "self-declared monthly revenue expectations against actual realized marketplace GMV and active seller counts."
    ),
)
def get_segment_performance(
    bypass_cache: bool = Query(
        False, description="Bypass in-memory cache and re-query the database"
    ),
    db: Session = Depends(get_db),
) -> SegmentPerformanceResponse:
    return MarketingService.get_segment_performance(db, bypass_cache=bypass_cache)


@router.get(
    "/leads",
    response_model=MarketingLeadsListResponse,
    summary="Browse Marketing Leads",
    description=(
        "Search and browse marketing qualified leads (MQL) with multi-faceted filtering "
        "by origin channel, deal won status, and business category segment."
    ),
)
def list_marketing_leads(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    origin: Optional[str] = Query(None, description="Filter by acquisition channel"),
    is_won: Optional[bool] = Query(None, description="Filter by won/lost status"),
    business_segment: Optional[str] = Query(
        None, description="Filter by business category segment"
    ),
    db: Session = Depends(get_db),
) -> MarketingLeadsListResponse:
    return MarketingService.list_leads(
        db=db,
        page=page,
        page_size=page_size,
        origin=origin,
        is_won=is_won,
        business_segment=business_segment,
    )
