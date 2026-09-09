"""
backend/routers/sellers.py
==========================
Endpoints for marketplace seller intelligence, fulfillment scorecard metrics,
and seller directory searches with pagination and state filtering.
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.seller import SellerDetail, SellerListResponse
from backend.services.seller_service import SellerService

router = APIRouter(prefix="/api/sellers", tags=["Sellers"])


@router.get(
    "",
    response_model=SellerListResponse,
    summary="List Marketplace Sellers (Paginated)",
    description=(
        "Returns a paginated list of marketplace sellers with gross merchandise value, "
        "fulfilled orders, delivery delay averages, late delivery rates, and review ratings."
    ),
)
def list_sellers(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    state: Optional[str] = Query(None, description="Filter by two-letter Brazilian state (e.g. SP, RJ)"),
    sort_by: str = Query(
        "total_revenue",
        description="Sort field: total_revenue, total_orders_fulfilled, total_items_sold, avg_review_score, late_delivery_rate",
    ),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    search: Optional[str] = Query(None, description="Search by seller_id or city"),
    bypass_cache: bool = Query(False, description="Bypass in-memory cache and force live database query"),
    db: Session = Depends(get_db),
) -> SellerListResponse:
    return SellerService.get_sellers(
        db=db,
        page=page,
        page_size=page_size,
        state=state,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        bypass_cache=bypass_cache,
    )


@router.get(
    "/{seller_id}",
    response_model=SellerDetail,
    summary="Seller 360 Profile",
    description=(
        "Returns complete performance profile for a specific marketplace seller, "
        "including top product categories, delivery delay rates, and review ratings."
    ),
)
def get_seller_detail(
    seller_id: str,
    bypass_cache: bool = Query(False, description="Bypass in-memory cache and force live database query"),
    db: Session = Depends(get_db),
) -> SellerDetail:
    seller = SellerService.get_seller_detail(db, seller_id=seller_id, bypass_cache=bypass_cache)
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seller with id '{seller_id}' was not found.",
        )
    return seller
