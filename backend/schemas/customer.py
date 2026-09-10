"""
backend/schemas/customer.py
===========================
Pydantic schemas for customer profiles, metrics, list summaries, and detail responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.churn import ChurnPrediction
from backend.schemas.common import PaginationMeta
from backend.schemas.rfm import RFMScorecard


class CustomerBasketMetrics(BaseModel):
    """Customer basket diversity and volume metrics."""

    model_config = ConfigDict(from_attributes=True)

    lifetime_items: int = Field(0, description="Total units/items purchased across all orders")
    avg_items_per_order: float = Field(0.0, description="Average items per order")
    total_unique_products_purchased: int = Field(0, description="Distinct product IDs purchased")
    total_unique_sellers_contacted: int = Field(
        0, description="Distinct marketplace sellers purchased from"
    )


class CustomerFulfillmentMetrics(BaseModel):
    """Fulfillment speed, delivery delays, and shipping friction metrics."""

    model_config = ConfigDict(from_attributes=True)

    avg_delivery_delay_days: Optional[float] = Field(
        None, description="Average delivery delay in days vs estimated date"
    )
    max_delivery_delay_days: Optional[float] = Field(
        None, description="Maximum delivery delay experienced in days"
    )
    late_orders_count: int = Field(0, description="Number of orders delivered past estimated date")
    late_order_ratio: float = Field(0.0, description="Proportion of orders delivered late")
    has_late_delivery: int = Field(
        0, description="1 if customer experienced at least one late delivery, else 0"
    )


class CustomerReviewMetrics(BaseModel):
    """Customer feedback and sentiment satisfaction metrics."""

    model_config = ConfigDict(from_attributes=True)

    total_reviews_submitted: int = Field(0, description="Total order reviews submitted")
    avg_review_score: Optional[float] = Field(None, description="Average review rating (1 to 5)")
    negative_reviews_count: int = Field(0, description="Count of negative reviews (rating <= 2)")
    positive_reviews_count: int = Field(0, description="Count of positive reviews (rating >= 4)")
    has_negative_review: int = Field(
        0, description="1 if customer gave at least one negative review, else 0"
    )
    negative_review_ratio: float = Field(
        0.0, description="Ratio of negative reviews to total submitted"
    )


class CustomerSummary(BaseModel):
    """Condensed customer summary for table views and paginated listings."""

    model_config = ConfigDict(from_attributes=True)

    customer_unique_id: str = Field(..., description="Unique returning customer identifier")
    city: Optional[str] = Field(None, description="Customer primary city")
    state: Optional[str] = Field(None, description="Customer primary state abbreviation")
    zip_prefix: Optional[str] = Field(None, description="Five-digit zip code prefix")
    first_purchased_at: Optional[Union[datetime, str]] = Field(
        None, description="Timestamp of first order"
    )
    latest_purchased_at: Optional[Union[datetime, str]] = Field(
        None, description="Timestamp of latest order"
    )
    recency_days: Optional[float] = Field(None, description="Days since latest purchase")
    customer_lifespan_days: Optional[float] = Field(
        None, description="Days between first and latest purchase"
    )
    lifetime_orders: int = Field(..., description="Total completed orders")
    is_repeat_buyer: int = Field(..., description="1 if >=2 orders, else 0")
    lifetime_spend: float = Field(..., description="Total gross spend in BRL")
    avg_order_value: float = Field(..., description="Average spend per order in BRL")

    # Joined RFM & Churn intelligence
    segment: Optional[str] = Field(None, description="Assigned RFM customer segment")
    churn_probability: Optional[float] = Field(
        None, description="Predicted churn probability P(Churn)"
    )
    risk_tier: Optional[str] = Field(None, description="Churn risk tier (High / Medium / Low)")
    revenue_at_risk: Optional[float] = Field(None, description="Monetary value at risk in BRL")
    retention_priority: Optional[str] = Field(
        None, description="Prescribed retention priority action"
    )


class CustomerDetail(BaseModel):
    """Comprehensive 360-degree customer intelligence profile."""

    model_config = ConfigDict(from_attributes=True)

    customer_unique_id: str = Field(..., description="Unique returning customer identifier")
    city: Optional[str] = Field(None, description="Customer primary city")
    state: Optional[str] = Field(None, description="Customer primary state abbreviation")
    zip_prefix: Optional[str] = Field(None, description="Five-digit zip code prefix")
    first_purchased_at: Optional[Union[datetime, str]] = Field(
        None, description="Timestamp of first order"
    )
    latest_purchased_at: Optional[Union[datetime, str]] = Field(
        None, description="Timestamp of latest order"
    )
    recency_days: Optional[float] = Field(None, description="Days since latest purchase")
    customer_lifespan_days: Optional[float] = Field(
        None, description="Days between first and latest purchase"
    )
    lifetime_orders: int = Field(..., description="Total completed orders")
    is_repeat_buyer: int = Field(..., description="1 if >=2 orders, else 0")
    lifetime_spend: float = Field(..., description="Total gross spend in BRL")
    lifetime_product_spend: float = Field(0.0, description="Spend on product items in BRL")
    lifetime_freight_spend: float = Field(0.0, description="Spend on shipping/freight in BRL")
    avg_order_value: float = Field(..., description="Average spend per order in BRL")

    # Sub-component metrics
    basket: CustomerBasketMetrics = Field(..., description="Basket volume and product diversity")
    fulfillment: CustomerFulfillmentMetrics = Field(
        ..., description="Delivery speed and delay friction"
    )
    reviews: CustomerReviewMetrics = Field(..., description="Review ratings and sentiment")

    # Linked ML outputs
    rfm: Optional[RFMScorecard] = Field(
        None, description="Complete RFM quintile scores and segment"
    )
    churn: Optional[ChurnPrediction] = Field(
        None, description="Churn risk score and revenue at risk"
    )


class CustomerListResponse(BaseModel):
    """Paginated list of customer summaries with query metadata."""

    model_config = ConfigDict(from_attributes=True)

    items: List[CustomerSummary] = Field(..., description="List of customers for the current page")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
