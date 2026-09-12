"""
backend/services/marketing_service.py
=====================================
Database queries and analytics service for two-sided marketplace marketing funnel,
seller acquisition velocity, channel attribution, and lead intelligence.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.cache import cached
from backend.schemas.common import PaginationMeta
from backend.schemas.marketing import (
    ChannelAttribution,
    ChannelAttributionResponse,
    MarketingFunnelOverview,
    MarketingLeadsListResponse,
    MarketingLeadSummary,
    SalesVelocityMetrics,
    SegmentPerformance,
    SegmentPerformanceResponse,
    VelocityByLeadType,
    VelocityBySegment,
)

log = logging.getLogger(__name__)


class MarketingService:
    """Service providing marketplace marketing funnel, attribution, and seller acquisition analytics."""

    @staticmethod
    @cached(ttl=300)
    def get_funnel_overview(db: Session, bypass_cache: bool = False) -> MarketingFunnelOverview:
        """Calculate macro seller acquisition funnel performance KPIs."""
        query = text(
            """
            SELECT
                COUNT(*)::INTEGER                                             AS total_leads,
                COUNT(CASE WHEN is_won THEN 1 END)::INTEGER                   AS total_closed_deals,
                ROUND(
                    COALESCE(
                        COUNT(CASE WHEN is_won THEN 1 END)::numeric / NULLIF(COUNT(*), 0) * 100.0,
                        0.0
                    ), 2
                )::FLOAT                                                      AS overall_conversion_rate,
                ROUND(
                    COALESCE(AVG(days_to_close), 0.0)::numeric, 1
                )::FLOAT                                                      AS avg_days_to_close,
                ROUND(
                    COALESCE(SUM(declared_monthly_revenue), 0.0)::numeric, 2
                )::FLOAT                                                      AS total_declared_monthly_revenue,
                ROUND(
                    COALESCE(SUM(actual_marketplace_revenue), 0.0)::numeric, 2
                )::FLOAT                                                      AS total_actual_marketplace_revenue,
                COUNT(CASE WHEN is_active_marketplace_seller THEN 1 END)::INTEGER AS active_marketplace_sellers_count,
                ROUND(
                    COALESCE(
                        COUNT(CASE WHEN is_active_marketplace_seller THEN 1 END)::numeric
                        / NULLIF(COUNT(CASE WHEN is_won THEN 1 END), 0) * 100.0,
                        0.0
                    ), 2
                )::FLOAT                                                      AS seller_activation_rate
            FROM mart.mart_marketing_funnel
            """
        )
        row = db.execute(query).mappings().first()
        if not row or row["total_leads"] == 0:
            return MarketingFunnelOverview(
                total_leads=0,
                total_closed_deals=0,
                overall_conversion_rate=0.0,
                avg_days_to_close=0.0,
                total_declared_monthly_revenue=0.0,
                total_actual_marketplace_revenue=0.0,
                active_marketplace_sellers_count=0,
                seller_activation_rate=0.0,
            )

        return MarketingFunnelOverview(
            total_leads=int(row["total_leads"] or 0),
            total_closed_deals=int(row["total_closed_deals"] or 0),
            overall_conversion_rate=float(row["overall_conversion_rate"] or 0.0),
            avg_days_to_close=float(row["avg_days_to_close"] or 0.0),
            total_declared_monthly_revenue=float(row["total_declared_monthly_revenue"] or 0.0),
            total_actual_marketplace_revenue=float(row["total_actual_marketplace_revenue"] or 0.0),
            active_marketplace_sellers_count=int(row["active_marketplace_sellers_count"] or 0),
            seller_activation_rate=float(row["seller_activation_rate"] or 0.0),
        )

    @staticmethod
    @cached(ttl=300)
    def get_channel_attribution(
        db: Session, bypass_cache: bool = False
    ) -> ChannelAttributionResponse:
        """Calculate acquisition origin channel breakdown with lead share and conversion rates."""
        query = text(
            """
            WITH totals AS (
                SELECT COUNT(*) AS global_leads FROM mart.mart_marketing_funnel
            )
            SELECT
                f.origin,
                COUNT(*)::INTEGER                                             AS leads_count,
                COUNT(CASE WHEN f.is_won THEN 1 END)::INTEGER                 AS closed_deals_count,
                ROUND(
                    COALESCE(
                        COUNT(CASE WHEN f.is_won THEN 1 END)::numeric / NULLIF(COUNT(*), 0) * 100.0,
                        0.0
                    ), 2
                )::FLOAT                                                      AS conversion_rate,
                ROUND(COALESCE(AVG(f.days_to_close), 0.0)::numeric, 1)::FLOAT AS avg_days_to_close,
                ROUND(
                    COALESCE(SUM(f.declared_monthly_revenue), 0.0)::numeric, 2
                )::FLOAT                                                      AS total_declared_monthly_revenue,
                ROUND(
                    COALESCE(SUM(f.actual_marketplace_revenue), 0.0)::numeric, 2
                )::FLOAT                                                      AS total_actual_marketplace_revenue,
                ROUND(
                    COALESCE(
                        COUNT(*)::numeric / NULLIF((SELECT global_leads FROM totals), 0) * 100.0,
                        0.0
                    ), 2
                )::FLOAT                                                      AS share_of_leads_percent
            FROM mart.mart_marketing_funnel f
            GROUP BY f.origin
            ORDER BY closed_deals_count DESC, leads_count DESC
            """
        )
        rows = db.execute(query).mappings().all()
        channels = [
            ChannelAttribution(
                origin=str(r["origin"]),
                leads_count=int(r["leads_count"] or 0),
                closed_deals_count=int(r["closed_deals_count"] or 0),
                conversion_rate=float(r["conversion_rate"] or 0.0),
                avg_days_to_close=float(r["avg_days_to_close"] or 0.0),
                total_declared_monthly_revenue=float(r["total_declared_monthly_revenue"] or 0.0),
                total_actual_marketplace_revenue=float(
                    r["total_actual_marketplace_revenue"] or 0.0
                ),
                share_of_leads_percent=float(r["share_of_leads_percent"] or 0.0),
            )
            for r in rows
        ]
        return ChannelAttributionResponse(channels=channels, total_channels=len(channels))

    @staticmethod
    @cached(ttl=300)
    def get_sales_velocity(db: Session, bypass_cache: bool = False) -> SalesVelocityMetrics:
        """Calculate sales cycle duration metrics segmented by category and lead type."""
        global_query = text(
            """
            SELECT ROUND(COALESCE(AVG(days_to_close), 0.0)::numeric, 1)::FLOAT AS overall_avg
            FROM mart.mart_marketing_funnel
            WHERE is_won IS TRUE
            """
        )
        overall_avg = db.execute(global_query).scalar() or 0.0

        segment_query = text(
            """
            SELECT
                COALESCE(business_segment, 'other')                           AS business_segment,
                COUNT(*)::INTEGER                                             AS closed_deals_count,
                ROUND(COALESCE(AVG(days_to_close), 0.0)::numeric, 1)::FLOAT   AS avg_days_to_close,
                COALESCE(MIN(days_to_close), 0)::INTEGER                      AS min_days_to_close,
                COALESCE(MAX(days_to_close), 0)::INTEGER                      AS max_days_to_close
            FROM mart.mart_marketing_funnel
            WHERE is_won IS TRUE AND business_segment IS NOT NULL
            GROUP BY business_segment
            ORDER BY avg_days_to_close ASC
            """
        )
        seg_rows = db.execute(segment_query).mappings().all()
        velocity_by_segment = [
            VelocityBySegment(
                business_segment=str(r["business_segment"]),
                closed_deals_count=int(r["closed_deals_count"] or 0),
                avg_days_to_close=float(r["avg_days_to_close"] or 0.0),
                min_days_to_close=int(r["min_days_to_close"] or 0),
                max_days_to_close=int(r["max_days_to_close"] or 0),
            )
            for r in seg_rows
        ]

        lead_type_query = text(
            """
            SELECT
                COALESCE(lead_type, 'unknown')                                AS lead_type,
                COUNT(*)::INTEGER                                             AS closed_deals_count,
                ROUND(COALESCE(AVG(days_to_close), 0.0)::numeric, 1)::FLOAT   AS avg_days_to_close
            FROM mart.mart_marketing_funnel
            WHERE is_won IS TRUE AND lead_type IS NOT NULL
            GROUP BY lead_type
            ORDER BY avg_days_to_close ASC
            """
        )
        lt_rows = db.execute(lead_type_query).mappings().all()
        velocity_by_lead_type = [
            VelocityByLeadType(
                lead_type=str(r["lead_type"]),
                closed_deals_count=int(r["closed_deals_count"] or 0),
                avg_days_to_close=float(r["avg_days_to_close"] or 0.0),
            )
            for r in lt_rows
        ]

        fastest = velocity_by_segment[0].business_segment if velocity_by_segment else None
        slowest = velocity_by_segment[-1].business_segment if velocity_by_segment else None

        return SalesVelocityMetrics(
            overall_avg_days_to_close=float(overall_avg),
            fastest_segment=fastest,
            slowest_segment=slowest,
            velocity_by_segment=velocity_by_segment,
            velocity_by_lead_type=velocity_by_lead_type,
        )

    @staticmethod
    @cached(ttl=300)
    def get_segment_performance(
        db: Session, bypass_cache: bool = False
    ) -> SegmentPerformanceResponse:
        """Calculate business category economic performance and marketplace GMV realization."""
        query = text(
            """
            SELECT
                COALESCE(business_segment, 'other')                           AS business_segment,
                COUNT(CASE WHEN is_won THEN 1 END)::INTEGER                   AS closed_deals_count,
                ROUND(
                    COALESCE(SUM(declared_monthly_revenue), 0.0)::numeric, 2
                )::FLOAT                                                      AS total_declared_monthly_revenue,
                ROUND(
                    COALESCE(AVG(declared_monthly_revenue), 0.0)::numeric, 2
                )::FLOAT                                                      AS avg_declared_monthly_revenue,
                ROUND(
                    COALESCE(SUM(actual_marketplace_revenue), 0.0)::numeric, 2
                )::FLOAT                                                      AS total_actual_marketplace_revenue,
                COUNT(CASE WHEN is_active_marketplace_seller THEN 1 END)::INTEGER AS active_sellers_count
            FROM mart.mart_marketing_funnel
            WHERE is_won IS TRUE
            GROUP BY business_segment
            ORDER BY total_actual_marketplace_revenue DESC, closed_deals_count DESC
            """
        )
        rows = db.execute(query).mappings().all()
        segments = [
            SegmentPerformance(
                business_segment=str(r["business_segment"]),
                closed_deals_count=int(r["closed_deals_count"] or 0),
                total_declared_monthly_revenue=float(r["total_declared_monthly_revenue"] or 0.0),
                avg_declared_monthly_revenue=float(r["avg_declared_monthly_revenue"] or 0.0),
                total_actual_marketplace_revenue=float(
                    r["total_actual_marketplace_revenue"] or 0.0
                ),
                active_sellers_count=int(r["active_sellers_count"] or 0),
            )
            for r in rows
        ]
        return SegmentPerformanceResponse(segments=segments, total_segments=len(segments))

    @staticmethod
    def list_leads(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        origin: Optional[str] = None,
        is_won: Optional[bool] = None,
        business_segment: Optional[str] = None,
    ) -> MarketingLeadsListResponse:
        """Search and browse marketing qualified leads with multi-faceted filtering."""
        page = max(1, page)
        page_size = max(1, min(100, page_size))
        offset = (page - 1) * page_size

        where_clauses: List[str] = []
        params: Dict[str, Any] = {"limit": page_size, "offset": offset}

        if origin:
            where_clauses.append("LOWER(origin) = :origin")
            params["origin"] = origin.lower()

        if is_won is not None:
            where_clauses.append("is_won = :is_won")
            params["is_won"] = is_won

        if business_segment:
            where_clauses.append("LOWER(business_segment) = :business_segment")
            params["business_segment"] = business_segment.lower()

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_query = text(f"SELECT COUNT(*) FROM mart.mart_marketing_funnel {where_sql}")
        total_items = db.execute(count_query, params).scalar() or 0

        data_query = text(
            f"""
            SELECT
                mql_id,
                first_contact_date::text AS first_contact_date,
                landing_page_id,
                origin,
                is_won,
                won_date::text           AS won_date,
                days_to_close,
                seller_id,
                business_segment,
                lead_type,
                declared_monthly_revenue,
                is_active_marketplace_seller,
                actual_marketplace_revenue
            FROM mart.mart_marketing_funnel
            {where_sql}
            ORDER BY first_contact_date DESC NULLS LAST, mql_id ASC
            LIMIT :limit OFFSET :offset
            """
        )
        rows = db.execute(data_query, params).mappings().all()

        items = [
            MarketingLeadSummary(
                mql_id=r["mql_id"],
                first_contact_date=r["first_contact_date"],
                landing_page_id=r["landing_page_id"],
                origin=r["origin"],
                is_won=bool(r["is_won"]),
                won_date=r["won_date"],
                days_to_close=r["days_to_close"],
                seller_id=r["seller_id"],
                business_segment=r["business_segment"],
                lead_type=r["lead_type"],
                declared_monthly_revenue=(
                    float(r["declared_monthly_revenue"])
                    if r["declared_monthly_revenue"] is not None
                    else None
                ),
                is_active_marketplace_seller=bool(r["is_active_marketplace_seller"]),
                actual_marketplace_revenue=(
                    float(r["actual_marketplace_revenue"])
                    if r["actual_marketplace_revenue"] is not None
                    else None
                ),
            )
            for r in rows
        ]

        pagination = PaginationMeta.create(
            page=page, page_size=page_size, total_items=int(total_items)
        )
        return MarketingLeadsListResponse(items=items, pagination=pagination)
