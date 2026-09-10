"""
backend/schemas/product.py
==========================
Pydantic schemas for product catalog intelligence and category analytics.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.common import PaginationMeta


class ProductSummary(BaseModel):
    """Performance summary and physical dimensions for a product catalog item."""

    model_config = ConfigDict(from_attributes=True)

    product_id: str = Field(..., description="Unique product identifier (UUID hex)")
    category_name_pt: Optional[str] = Field(None, description="Original Portuguese category name")
    category_name_en: Optional[str] = Field(None, description="English category name translation")
    total_units_sold: int = Field(0, description="Total units sold across all delivered orders")
    total_orders_count: int = Field(
        0, description="Distinct delivered orders containing this product"
    )
    total_revenue: float = Field(
        0.0, description="Gross revenue generated (price + freight) in BRL"
    )
    avg_unit_price: float = Field(0.0, description="Average retail price in BRL")
    avg_review_score: Optional[float] = Field(
        None, description="Average customer review rating (1.0 - 5.0)"
    )
    product_weight_g: Optional[float] = Field(None, description="Product weight in grams")
    product_length_cm: Optional[float] = Field(None, description="Product package length in cm")
    product_height_cm: Optional[float] = Field(None, description="Product package height in cm")
    product_width_cm: Optional[float] = Field(None, description="Product package width in cm")
    product_photos_qty: Optional[int] = Field(
        None, description="Number of product gallery photos published"
    )


class CategorySummary(BaseModel):
    """Macro performance metrics for a product category."""

    model_config = ConfigDict(from_attributes=True)

    category: str = Field(..., description="English category slug or name")
    category_pt: Optional[str] = Field(None, description="Original Portuguese category name")
    total_products: int = Field(..., description="Total distinct product catalog items in category")
    total_units_sold: int = Field(..., description="Total units sold in category")
    total_revenue: float = Field(..., description="Gross category revenue in BRL")
    avg_price: float = Field(..., description="Average item selling price in BRL")
    avg_review_score: Optional[float] = Field(None, description="Average category review score")


class ProductListResponse(BaseModel):
    """Paginated list envelope for product catalog items."""

    model_config = ConfigDict(from_attributes=True)

    items: List[ProductSummary] = Field(..., description="Products matching query filters")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class CategoryListResponse(BaseModel):
    """Aggregate category list response."""

    model_config = ConfigDict(from_attributes=True)

    total_categories: int = Field(..., description="Number of distinct product categories")
    categories: List[CategorySummary] = Field(..., description="Category performance summaries")
