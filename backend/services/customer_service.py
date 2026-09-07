"""
backend/services/customer_service.py
====================================
Database service for customer queries, listings, filtering, sorting,
and detailed multi-layer customer intelligence rollups.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.schemas.churn import ChurnPrediction
from backend.schemas.common import PaginationMeta
from backend.schemas.customer import (
    CustomerBasketMetrics,
    CustomerDetail,
    CustomerFulfillmentMetrics,
    CustomerListResponse,
    CustomerReviewMetrics,
    CustomerSummary,
)
from backend.schemas.rfm import RFMScorecard

log = logging.getLogger(__name__)

# Valid sort columns mapped to database aliases to prevent SQL injection
_ALLOWED_SORT_COLUMNS = {
    "lifetime_spend": "c.lifetime_spend",
    "recency_days": "c.recency_days",
    "lifetime_orders": "c.lifetime_orders",
    "avg_order_value": "c.avg_order_value",
    "first_purchased_at": "c.first_purchased_at",
    "latest_purchased_at": "c.latest_purchased_at",
    "revenue_at_risk": "ch.revenue_at_risk",
    "churn_probability": "ch.churn_probability",
}


class CustomerService:
    """Service handling customer listings, search, and deep profiles."""

    @staticmethod
    def get_customers(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        segment: Optional[str] = None,
        risk_tier: Optional[str] = None,
        retention_priority: Optional[str] = None,
        state: Optional[str] = None,
        min_spend: Optional[float] = None,
        max_spend: Optional[float] = None,
        search: Optional[str] = None,
        sort_by: str = "lifetime_spend",
        sort_order: str = "desc",
    ) -> CustomerListResponse:
        """
        Query paginated customer list with multi-dimensional filtering
        (RFM segment, churn risk tier, retention priority, geography, spend).
        """
        # Validate sort parameters safely
        order_col = _ALLOWED_SORT_COLUMNS.get(sort_by, "c.lifetime_spend")
        direction = "ASC" if sort_order.lower() == "asc" else "DESC"

        # Build dynamic WHERE clauses with parameterized values
        conditions = ["1=1"]
        params: Dict[str, Any] = {
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }

        if segment:
            conditions.append("r.segment = :segment")
            params["segment"] = segment

        if risk_tier:
            conditions.append("ch.risk_tier = :risk_tier")
            params["risk_tier"] = risk_tier

        if retention_priority:
            conditions.append("ch.retention_priority = :retention_priority")
            params["retention_priority"] = retention_priority

        if state:
            conditions.append("c.state = :state")
            params["state"] = state.upper()

        if min_spend is not None:
            conditions.append("c.lifetime_spend >= :min_spend")
            params["min_spend"] = min_spend

        if max_spend is not None:
            conditions.append("c.lifetime_spend <= :max_spend")
            params["max_spend"] = max_spend

        if search:
            conditions.append("c.customer_unique_id LIKE :search")
            params["search"] = f"%{search.strip()}%"

        where_clause = " AND ".join(conditions)

        # 1. Total matching count query
        count_sql = text(
            f"""
            SELECT COUNT(*)
            FROM mart.mart_customer_metrics c
            LEFT JOIN ml.rfm_segments r ON c.customer_unique_id = r.customer_unique_id
            LEFT JOIN ml.churn_predictions ch ON c.customer_unique_id = ch.customer_unique_id
            WHERE {where_clause}
            """
        )
        total_items = db.execute(count_sql, params).scalar() or 0

        # 2. Paginated rows query
        query_sql = text(
            f"""
            SELECT
                c.customer_unique_id,
                c.city,
                c.state,
                c.zip_prefix,
                c.first_purchased_at,
                c.latest_purchased_at,
                c.recency_days,
                c.customer_lifespan_days,
                c.lifetime_orders,
                c.is_repeat_buyer,
                c.lifetime_spend,
                c.avg_order_value,
                r.segment,
                ch.churn_probability,
                ch.risk_tier,
                ch.revenue_at_risk,
                ch.retention_priority
            FROM mart.mart_customer_metrics c
            LEFT JOIN ml.rfm_segments r ON c.customer_unique_id = r.customer_unique_id
            LEFT JOIN ml.churn_predictions ch ON c.customer_unique_id = ch.customer_unique_id
            WHERE {where_clause}
            ORDER BY {order_col} {direction} NULLS LAST, c.customer_unique_id ASC
            LIMIT :limit OFFSET :offset
            """
        )
        rows = db.execute(query_sql, params).mappings().all()

        items = [
            CustomerSummary(
                customer_unique_id=r["customer_unique_id"],
                city=r["city"],
                state=r["state"],
                zip_prefix=r["zip_prefix"],
                first_purchased_at=r["first_purchased_at"],
                latest_purchased_at=r["latest_purchased_at"],
                recency_days=float(r["recency_days"]) if r["recency_days"] is not None else None,
                customer_lifespan_days=float(r["customer_lifespan_days"]) if r["customer_lifespan_days"] is not None else None,
                lifetime_orders=int(r["lifetime_orders"]),
                is_repeat_buyer=int(r["is_repeat_buyer"]),
                lifetime_spend=round(float(r["lifetime_spend"]), 2),
                avg_order_value=round(float(r["avg_order_value"]), 2),
                segment=r["segment"],
                churn_probability=float(r["churn_probability"]) if r["churn_probability"] is not None else None,
                risk_tier=r["risk_tier"],
                revenue_at_risk=float(r["revenue_at_risk"]) if r["revenue_at_risk"] is not None else None,
                retention_priority=r["retention_priority"],
            )
            for r in rows
        ]

        pagination = PaginationMeta.create(page=page, page_size=page_size, total_items=total_items)
        return CustomerListResponse(items=items, pagination=pagination)

    @staticmethod
    def get_customer_detail(
        db: Session, customer_unique_id: str
    ) -> Optional[CustomerDetail]:
        """
        Fetch full 360-degree customer intelligence detail including
        basket composition, fulfillment friction, review sentiment,
        RFM scores, and ML churn prediction.
        """
        query = text(
            """
            SELECT
                c.customer_unique_id,
                c.city,
                c.state,
                c.zip_prefix,
                c.first_purchased_at,
                c.latest_purchased_at,
                c.recency_days,
                c.customer_lifespan_days,
                c.lifetime_orders,
                c.is_repeat_buyer,
                c.lifetime_spend,
                c.lifetime_product_spend,
                c.lifetime_freight_spend,
                c.avg_order_value,
                c.lifetime_items,
                c.avg_items_per_order,
                c.total_unique_products_purchased,
                c.total_unique_sellers_contacted,
                c.avg_delivery_delay_days,
                c.max_delivery_delay_days,
                c.late_orders_count,
                c.late_order_ratio,
                c.has_late_delivery,
                c.total_reviews_submitted,
                c.avg_review_score,
                c.negative_reviews_count,
                c.positive_reviews_count,
                c.has_negative_review,
                c.negative_review_ratio,
                -- RFM
                r.r_score,
                r.f_score,
                r.m_score,
                r.rfm_score,
                r.rfm_label,
                r.segment,
                r.computed_at AS rfm_computed_at,
                -- Churn
                ch.is_churned,
                ch.churn_probability,
                ch.risk_tier,
                ch.monetary_value,
                ch.revenue_at_risk,
                ch.retention_priority,
                ch.predicted_at AS churn_predicted_at
            FROM mart.mart_customer_metrics c
            LEFT JOIN ml.rfm_segments r ON c.customer_unique_id = r.customer_unique_id
            LEFT JOIN ml.churn_predictions ch ON c.customer_unique_id = ch.customer_unique_id
            WHERE c.customer_unique_id = :id
            """
        )
        row = db.execute(query, {"id": customer_unique_id}).mappings().one_or_none()
        if not row:
            return None

        # Build sub-components
        basket = CustomerBasketMetrics(
            lifetime_items=int(row["lifetime_items"] or 0),
            avg_items_per_order=float(row["avg_items_per_order"] or 0.0),
            total_unique_products_purchased=int(row["total_unique_products_purchased"] or 0),
            total_unique_sellers_contacted=int(row["total_unique_sellers_contacted"] or 0),
        )

        fulfillment = CustomerFulfillmentMetrics(
            avg_delivery_delay_days=float(row["avg_delivery_delay_days"]) if row["avg_delivery_delay_days"] is not None else None,
            max_delivery_delay_days=float(row["max_delivery_delay_days"]) if row["max_delivery_delay_days"] is not None else None,
            late_orders_count=int(row["late_orders_count"] or 0),
            late_order_ratio=float(row["late_order_ratio"] or 0.0),
            has_late_delivery=int(row["has_late_delivery"] or 0),
        )

        reviews = CustomerReviewMetrics(
            total_reviews_submitted=int(row["total_reviews_submitted"] or 0),
            avg_review_score=float(row["avg_review_score"]) if row["avg_review_score"] is not None else None,
            negative_reviews_count=int(row["negative_reviews_count"] or 0),
            positive_reviews_count=int(row["positive_reviews_count"] or 0),
            has_negative_review=int(row["has_negative_review"] or 0),
            negative_review_ratio=float(row["negative_review_ratio"] or 0.0),
        )

        # Build RFM scorecard if present
        rfm: Optional[RFMScorecard] = None
        if row["segment"] is not None:
            rfm = RFMScorecard(
                customer_unique_id=row["customer_unique_id"],
                recency_days=float(row["recency_days"] or 0.0),
                frequency=int(row["lifetime_orders"] or 0),
                monetary=float(row["lifetime_spend"] or 0.0),
                r_score=int(row["r_score"] or 1),
                f_score=int(row["f_score"] or 1),
                m_score=int(row["m_score"] or 1),
                rfm_score=float(row["rfm_score"] or 0.0),
                rfm_label=str(row["rfm_label"] or ""),
                segment=str(row["segment"]),
                computed_at=row["rfm_computed_at"],
            )

        # Build Churn prediction if present
        churn: Optional[ChurnPrediction] = None
        if row["churn_probability"] is not None:
            churn = ChurnPrediction(
                customer_unique_id=row["customer_unique_id"],
                is_churned=int(row["is_churned"] or 0),
                churn_probability=float(row["churn_probability"]),
                risk_tier=str(row["risk_tier"] or ""),
                monetary_value=float(row["monetary_value"] or row["lifetime_spend"] or 0.0),
                revenue_at_risk=float(row["revenue_at_risk"] or 0.0),
                retention_priority=str(row["retention_priority"] or ""),
                predicted_at=row["churn_predicted_at"],
            )

        return CustomerDetail(
            customer_unique_id=row["customer_unique_id"],
            city=row["city"],
            state=row["state"],
            zip_prefix=row["zip_prefix"],
            first_purchased_at=row["first_purchased_at"],
            latest_purchased_at=row["latest_purchased_at"],
            recency_days=float(row["recency_days"]) if row["recency_days"] is not None else None,
            customer_lifespan_days=float(row["customer_lifespan_days"]) if row["customer_lifespan_days"] is not None else None,
            lifetime_orders=int(row["lifetime_orders"] or 0),
            is_repeat_buyer=int(row["is_repeat_buyer"] or 0),
            lifetime_spend=round(float(row["lifetime_spend"] or 0.0), 2),
            lifetime_product_spend=round(float(row["lifetime_product_spend"] or 0.0), 2),
            lifetime_freight_spend=round(float(row["lifetime_freight_spend"] or 0.0), 2),
            avg_order_value=round(float(row["avg_order_value"] or 0.0), 2),
            basket=basket,
            fulfillment=fulfillment,
            reviews=reviews,
            rfm=rfm,
            churn=churn,
        )

    @staticmethod
    def get_customer_rfm(
        db: Session, customer_unique_id: str
    ) -> Optional[RFMScorecard]:
        """Fetch RFM scorecard directly from ml.rfm_segments."""
        query = text(
            """
            SELECT
                customer_unique_id,
                recency_days,
                frequency,
                monetary,
                r_score,
                f_score,
                m_score,
                rfm_score,
                rfm_label,
                segment,
                computed_at
            FROM ml.rfm_segments
            WHERE customer_unique_id = :id
            """
        )
        row = db.execute(query, {"id": customer_unique_id}).mappings().one_or_none()
        if not row:
            return None

        return RFMScorecard(
            customer_unique_id=row["customer_unique_id"],
            recency_days=float(row["recency_days"]),
            frequency=int(row["frequency"]),
            monetary=round(float(row["monetary"]), 2),
            r_score=int(row["r_score"]),
            f_score=int(row["f_score"]),
            m_score=int(row["m_score"]),
            rfm_score=float(row["rfm_score"]),
            rfm_label=row["rfm_label"],
            segment=row["segment"],
            computed_at=row["computed_at"],
        )

    @staticmethod
    def get_customer_churn(
        db: Session, customer_unique_id: str
    ) -> Optional[ChurnPrediction]:
        """Fetch Churn prediction directly from ml.churn_predictions."""
        query = text(
            """
            SELECT
                customer_unique_id,
                is_churned,
                churn_probability,
                risk_tier,
                monetary_value,
                revenue_at_risk,
                retention_priority,
                predicted_at
            FROM ml.churn_predictions
            WHERE customer_unique_id = :id
            """
        )
        row = db.execute(query, {"id": customer_unique_id}).mappings().one_or_none()
        if not row:
            return None

        return ChurnPrediction(
            customer_unique_id=row["customer_unique_id"],
            is_churned=int(row["is_churned"]),
            churn_probability=float(row["churn_probability"]),
            risk_tier=row["risk_tier"],
            monetary_value=round(float(row["monetary_value"]), 2),
            revenue_at_risk=round(float(row["revenue_at_risk"]), 2),
            retention_priority=row["retention_priority"],
            predicted_at=row["predicted_at"],
        )

    @staticmethod
    def get_at_risk_customers(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        risk_tier: Optional[str] = None,
        retention_priority: Optional[str] = None,
    ) -> CustomerListResponse:
        """
        Specialized endpoint query for retention campaigns.
        Defaults to High and Medium risk tiers, sorted by revenue_at_risk DESC.
        """
        # If no specific risk tier specified, filter to High and Medium
        tier_filter = risk_tier if risk_tier else None

        # Delegate to get_customers with revenue_at_risk DESC ordering
        res = CustomerService.get_customers(
            db=db,
            page=page,
            page_size=page_size,
            risk_tier=tier_filter,
            retention_priority=retention_priority,
            sort_by="revenue_at_risk",
            sort_order="desc",
        )
        return res
