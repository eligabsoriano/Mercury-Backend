"""
backend/routers/customers.py
============================
Customer endpoints for paginated search, multi-faceted filtering,
at-risk retention queues, and 360-degree customer intelligence profiles.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.analytics import SegmentsOverview
from backend.schemas.churn import ChurnPrediction
from backend.schemas.customer import (
    CustomerDetail,
    CustomerListResponse,
)
from backend.schemas.rfm import RFMScorecard
from backend.services.analytics_service import AnalyticsService
from backend.services.customer_service import CustomerService

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="List Customers (Paginated & Filtered)",
    description=(
        "Query customers with optional filtering by RFM segment, churn risk tier, "
        "retention priority, Brazilian state, spend range, or customer identifier search."
    ),
)
def list_customers(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    segment: Optional[str] = Query(None, description="Filter by RFM segment"),
    risk_tier: Optional[str] = Query(None, description="Filter by Churn Risk Tier (High, Medium, Low)"),
    retention_priority: Optional[str] = Query(None, description="Filter by Retention Priority Action"),
    state: Optional[str] = Query(None, description="Filter by 2-letter state abbreviation (e.g. SP, RJ)"),
    min_spend: Optional[float] = Query(None, ge=0.0, description="Minimum lifetime spend in BRL"),
    max_spend: Optional[float] = Query(None, ge=0.0, description="Maximum lifetime spend in BRL"),
    search: Optional[str] = Query(None, description="Search by customer_unique_id"),
    sort_by: str = Query(
        "lifetime_spend",
        description="Sort field: lifetime_spend, recency_days, lifetime_orders, avg_order_value, revenue_at_risk, churn_probability",
    ),
    sort_order: str = Query("desc", description="Sort order direction: asc or desc"),
    db: Session = Depends(get_db),
) -> CustomerListResponse:
    return CustomerService.get_customers(
        db=db,
        page=page,
        page_size=page_size,
        segment=segment,
        risk_tier=risk_tier,
        retention_priority=retention_priority,
        state=state,
        min_spend=min_spend,
        max_spend=max_spend,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/at-risk",
    response_model=CustomerListResponse,
    summary="At-Risk Customer Retention Queue",
    description=(
        "High-priority queue of customers with elevated churn probability, "
        "ordered by expected monetary revenue at risk (descending)."
    ),
)
def get_at_risk_customers(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    risk_tier: Optional[str] = Query(None, description="Filter risk tier (High or Medium)"),
    retention_priority: Optional[str] = Query(None, description="Filter by retention priority action"),
    db: Session = Depends(get_db),
) -> CustomerListResponse:
    return CustomerService.get_at_risk_customers(
        db=db,
        page=page,
        page_size=page_size,
        risk_tier=risk_tier,
        retention_priority=retention_priority,
    )


@router.get(
    "/segments",
    response_model=SegmentsOverview,
    summary="Customer Segments Breakdown (Convenience Alias)",
    description="Returns aggregate RFM customer segmentation summary.",
)
def get_customer_segments_alias(
    bypass_cache: bool = Query(False, description="Bypass in-memory cache and force live database query"),
    db: Session = Depends(get_db),
) -> SegmentsOverview:
    return AnalyticsService.get_segments_overview(db, bypass_cache=bypass_cache)


@router.get(
    "/export",
    summary="Export Customers for CRM Campaigns (Streaming CSV)",
    description=(
        "Streams a formatted CSV export of customers with lifetime spend, churn risk tier, "
        "retention priority, and recommended action based on applied filters."
    ),
)
def export_customers_csv(
    segment: Optional[str] = Query(None, description="Filter by RFM segment"),
    risk_tier: Optional[str] = Query(None, description="Filter by churn risk tier (High, Medium, Low)"),
    retention_priority: Optional[str] = Query(None, description="Filter by retention priority action"),
    state: Optional[str] = Query(None, description="Filter by 2-letter state abbreviation"),
    min_spend: Optional[float] = Query(None, ge=0.0, description="Minimum lifetime spend in BRL"),
    max_spend: Optional[float] = Query(None, ge=0.0, description="Maximum lifetime spend in BRL"),
    format: str = Query("csv", description="Export format (csv)"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    generator = CustomerService.stream_customers_csv(
        db=db,
        segment=segment,
        risk_tier=risk_tier,
        retention_priority=retention_priority,
        state=state,
        min_spend=min_spend,
        max_spend=max_spend,
    )
    return StreamingResponse(
        generator,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mercury_customers_export.csv"},
    )



@router.get(
    "/{customer_unique_id}",
    response_model=CustomerDetail,
    summary="Customer 360 Profile",
    description=(
        "Returns complete customer profile: order history, basket metrics, "
        "fulfillment friction, review ratings, RFM scores, and ML churn prediction."
    ),
)
def get_customer_detail(
    customer_unique_id: str,
    db: Session = Depends(get_db),
) -> CustomerDetail:
    customer = CustomerService.get_customer_detail(db, customer_unique_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with unique id '{customer_unique_id}' was not found.",
        )
    return customer


@router.get(
    "/{customer_unique_id}/rfm",
    response_model=RFMScorecard,
    summary="Customer RFM Scorecard",
    description="Returns the RFM quintile scores, composite score, and segment for a customer.",
)
def get_customer_rfm(
    customer_unique_id: str,
    db: Session = Depends(get_db),
) -> RFMScorecard:
    rfm = CustomerService.get_customer_rfm(db, customer_unique_id)
    if not rfm:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RFM scorecard for customer '{customer_unique_id}' was not found.",
        )
    return rfm


@router.get(
    "/{customer_unique_id}/churn",
    response_model=ChurnPrediction,
    summary="Customer Churn Prediction",
    description="Returns the churn probability, risk tier, revenue at risk, and retention priority.",
)
def get_customer_churn(
    customer_unique_id: str,
    db: Session = Depends(get_db),
) -> ChurnPrediction:
    churn = CustomerService.get_customer_churn(db, customer_unique_id)
    if not churn:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Churn prediction for customer '{customer_unique_id}' was not found.",
        )
    return churn
