"""
backend/schemas/seller.py
=========================
Pydantic schemas for marketplace seller performance intelligence.
Includes seller metrics, fulfillment efficiency, and paginated responses.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.common import PaginationMeta


class SellerSummary(BaseModel):
    """Aggregate performance and fulfillment scorecard for a marketplace seller."""

    model_config = ConfigDict(from_attributes=True)

    seller_id: str = Field(..., description="Unique seller identifier (UUID hex)")
    city: Optional[str] = Field(None, description="Seller city")
    state: Optional[str] = Field(None, description="Two-letter Brazilian state abbreviation")
    zip_prefix: Optional[str] = Field(None, description="Seller 5-digit zip code prefix")
    total_orders_fulfilled: int = Field(
        0, description="Count of distinct delivered orders fulfilled"
    )
    total_items_sold: int = Field(0, description="Total units/line-items sold across orders")
    total_unique_products: int = Field(0, description="Distinct product catalog items sold")
    total_revenue: float = Field(
        0.0, description="Gross revenue generated (items + freight) in BRL"
    )
    avg_item_value: float = Field(0.0, description="Average order line-item value in BRL")
    avg_delivery_delay_days: Optional[float] = Field(
        None, description="Mean delivery delay in days relative to estimated delivery date"
    )
    late_delivery_rate: float = Field(
        0.0, description="Percentage of orders delivered past estimated date"
    )
    avg_review_score: Optional[float] = Field(
        None, description="Mean customer review rating (1.0 - 5.0)"
    )


class SellerDetail(SellerSummary):
    """Detailed 360-degree seller intelligence profile."""

    top_categories: List[str] = Field(
        default_factory=list, description="Top product categories sold by this seller"
    )
    positive_reviews_rate: float = Field(
        0.0, description="Percentage of customer reviews rated 4 or 5 stars"
    )


class SellerListResponse(BaseModel):
    """Paginated list envelope for seller summaries."""

    model_config = ConfigDict(from_attributes=True)

    items: List[SellerSummary] = Field(..., description="Sellers matching the filter criteria")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
