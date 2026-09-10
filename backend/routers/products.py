"""
backend/routers/products.py
===========================
Endpoints for product catalog intelligence, sales velocity analytics,
and category market share breakdowns.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.product import (
    CategoryListResponse,
    ProductListResponse,
    ProductSummary,
)
from backend.services.product_service import ProductService

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get(
    "",
    response_model=ProductListResponse,
    summary="List Product Catalog (Paginated)",
    description=(
        "Returns a paginated list of catalog products with sales volume, total revenue, "
        "average unit price, customer review ratings, and package specifications."
    ),
)
def list_products(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    category: Optional[str] = Query(
        None, description="Filter by category name (English or Portuguese)"
    ),
    sort_by: str = Query(
        "total_revenue",
        description="Sort field: total_revenue, total_units_sold, total_orders_count, avg_unit_price, avg_review_score",
    ),
    sort_order: str = Query("desc", description="Sort order: asc or desc"),
    search: Optional[str] = Query(None, description="Search by product_id or category"),
    bypass_cache: bool = Query(
        False, description="Bypass in-memory cache and force live database query"
    ),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    return ProductService.get_products(
        db=db,
        page=page,
        page_size=page_size,
        category=category,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        bypass_cache=bypass_cache,
    )


@router.get(
    "/categories",
    response_model=CategoryListResponse,
    summary="Product Categories Breakdown",
    description=(
        "Returns aggregate product sales performance and revenue contribution "
        "broken down across distinct marketplace merchandise categories."
    ),
)
def get_categories_overview(
    bypass_cache: bool = Query(
        False, description="Bypass in-memory cache and force live database query"
    ),
    db: Session = Depends(get_db),
) -> CategoryListResponse:
    return ProductService.get_categories(db=db, bypass_cache=bypass_cache)


@router.get(
    "/{product_id}",
    response_model=ProductSummary,
    summary="Product 360 Scorecard",
    description=(
        "Returns performance metrics, sales velocity, customer review ratings, "
        "and physical dimensions for an individual catalog product."
    ),
)
def get_product_detail(
    product_id: str,
    bypass_cache: bool = Query(
        False, description="Bypass in-memory cache and force live database query"
    ),
    db: Session = Depends(get_db),
) -> ProductSummary:
    product = ProductService.get_product_detail(
        db, product_id=product_id, bypass_cache=bypass_cache
    )
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id '{product_id}' was not found.",
        )
    return product
