"""
backend/schemas/marketing.py
============================
Pydantic v2 schemas for Phase 10: Two-Sided Marketplace Marketing Funnel,
Seller Acquisition Velocity, and Origin Channel Attribution.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from backend.schemas.common import PaginationMeta


class MarketingFunnelOverview(BaseModel):
    """Macro-level seller acquisition marketing funnel performance indicators."""

    total_leads: int = Field(..., description="Total marketing qualified leads (MQL) acquired")
    total_closed_deals: int = Field(..., description="Total converted deals won")
    overall_conversion_rate: float = Field(
        ...,
        description="Funnel conversion efficiency percentage (closed_deals / total_leads * 100)",
    )
    avg_days_to_close: float = Field(
        ..., description="Average sales cycle velocity from first contact to deal won in days"
    )
    total_declared_monthly_revenue: float = Field(
        ..., description="Aggregate self-declared monthly revenue of converted sellers (BRL)"
    )
    total_actual_marketplace_revenue: float = Field(
        ..., description="Aggregate actual realized marketplace GMV from converted sellers (BRL)"
    )
    active_marketplace_sellers_count: int = Field(
        ..., description="Count of converted sellers who actively fulfilled marketplace orders"
    )
    seller_activation_rate: float = Field(
        ..., description="Percentage of won deals that became active revenue-generating sellers"
    )


class ChannelAttribution(BaseModel):
    """Acquisition origin channel conversion and revenue attribution scorecard."""

    origin: str = Field(
        ..., description="Acquisition origin channel (e.g. organic_search, paid_search)"
    )
    leads_count: int = Field(..., description="Number of MQLs acquired through this channel")
    closed_deals_count: int = Field(..., description="Number of won deals from this channel")
    conversion_rate: float = Field(..., description="Conversion rate percentage for this channel")
    avg_days_to_close: float = Field(
        ..., description="Average sales velocity in days for this channel"
    )
    total_declared_monthly_revenue: float = Field(
        ..., description="Declared monthly revenue attributed to this channel (BRL)"
    )
    total_actual_marketplace_revenue: float = Field(
        ..., description="Realized marketplace GMV attributed to this channel (BRL)"
    )
    share_of_leads_percent: float = Field(
        ..., description="Channel share of total lead volume percentage"
    )


class ChannelAttributionResponse(BaseModel):
    """List of all acquisition origin channels ranked by conversion or volume."""

    channels: List[ChannelAttribution] = Field(
        ..., description="Origin channel attribution breakdowns"
    )
    total_channels: int = Field(..., description="Total distinct channels identified")


class VelocityBySegment(BaseModel):
    """Sales cycle velocity metrics aggregated by business segment."""

    business_segment: str = Field(..., description="Seller industry or catalog segment")
    closed_deals_count: int = Field(..., description="Total deals closed in segment")
    avg_days_to_close: float = Field(..., description="Mean days elapsed from MQL to closed deal")
    min_days_to_close: int = Field(..., description="Minimum days to close in segment")
    max_days_to_close: int = Field(..., description="Maximum days to close in segment")


class VelocityByLeadType(BaseModel):
    """Sales cycle velocity metrics aggregated by lead type."""

    lead_type: str = Field(..., description="Lead classification (e.g. online, offline, industry)")
    closed_deals_count: int = Field(..., description="Total deals closed of this lead type")
    avg_days_to_close: float = Field(..., description="Mean days to close for this lead type")


class SalesVelocityMetrics(BaseModel):
    """Comprehensive sales velocity indicators across segments and lead types."""

    overall_avg_days_to_close: float = Field(
        ..., description="Global average sales cycle duration across all won deals"
    )
    fastest_segment: Optional[str] = Field(
        None, description="Segment with the shortest average days to close"
    )
    slowest_segment: Optional[str] = Field(
        None, description="Segment with the longest average days to close"
    )
    velocity_by_segment: List[VelocityBySegment] = Field(
        ..., description="Velocity breakdowns per business segment"
    )
    velocity_by_lead_type: List[VelocityByLeadType] = Field(
        ..., description="Velocity breakdowns per lead type"
    )


class SegmentPerformance(BaseModel):
    """Marketplace seller category segment economic performance."""

    business_segment: str = Field(..., description="Business category segment")
    closed_deals_count: int = Field(..., description="Number of won deals in this segment")
    total_declared_monthly_revenue: float = Field(
        ..., description="Total self-declared monthly revenue (BRL)"
    )
    avg_declared_monthly_revenue: float = Field(
        ..., description="Average declared monthly revenue per seller (BRL)"
    )
    total_actual_marketplace_revenue: float = Field(
        ..., description="Total realized marketplace GMV from this segment (BRL)"
    )
    active_sellers_count: int = Field(
        ..., description="Count of sellers in this segment actively fulfilling orders"
    )


class SegmentPerformanceResponse(BaseModel):
    """Overview of business segments ordered by volume or revenue."""

    segments: List[SegmentPerformance] = Field(..., description="Segment performance summaries")
    total_segments: int = Field(..., description="Total distinct business segments")


class MarketingLeadSummary(BaseModel):
    """Individual marketing qualified lead record."""

    mql_id: str = Field(..., description="Marketing qualified lead identifier")
    first_contact_date: Optional[str] = Field(None, description="Initial contact date")
    landing_page_id: Optional[str] = Field(None, description="Landing page identifier")
    origin: str = Field(..., description="Acquisition origin channel")
    is_won: bool = Field(..., description="Whether deal was won")
    won_date: Optional[str] = Field(None, description="Date deal closed, if won")
    days_to_close: Optional[int] = Field(None, description="Duration from lead to close in days")
    seller_id: Optional[str] = Field(None, description="Matched seller identifier, if won")
    business_segment: Optional[str] = Field(None, description="Segment classification")
    lead_type: Optional[str] = Field(None, description="Lead category type")
    declared_monthly_revenue: Optional[float] = Field(
        None, description="Self-declared monthly revenue (BRL)"
    )
    is_active_marketplace_seller: bool = Field(
        ..., description="True if seller generated actual marketplace transactions"
    )
    actual_marketplace_revenue: Optional[float] = Field(
        None, description="Actual realized marketplace revenue (BRL)"
    )


class MarketingLeadsListResponse(BaseModel):
    """Paginated collection of marketing qualified leads."""

    items: List[MarketingLeadSummary] = Field(..., description="Marketing lead records")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
