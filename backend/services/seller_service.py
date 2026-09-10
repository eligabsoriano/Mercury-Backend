"""
backend/services/seller_service.py
==================================
Database query service for marketplace seller intelligence and fulfillment metrics.
Aggregates order volumes, revenue, delivery delays, and review ratings.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.cache import cached
from backend.schemas.common import PaginationMeta
from backend.schemas.seller import SellerDetail, SellerListResponse, SellerSummary

log = logging.getLogger(__name__)


class SellerService:
    """Service providing marketplace seller performance analytics."""

    _ALLOWED_SORT_COLUMNS = {
        "total_revenue": "total_revenue",
        "total_orders_fulfilled": "total_orders_fulfilled",
        "total_items_sold": "total_items_sold",
        "avg_review_score": "avg_review_score",
        "late_delivery_rate": "late_delivery_rate",
        "avg_item_value": "avg_item_value",
    }

    @staticmethod
    @cached(ttl=300)
    def get_sellers(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        state: Optional[str] = None,
        sort_by: str = "total_revenue",
        sort_order: str = "desc",
        search: Optional[str] = None,
        bypass_cache: bool = False,
    ) -> SellerListResponse:
        """
        Fetch paginated list of marketplace sellers with aggregate fulfillment, revenue, and review metrics.
        """
        where_clauses: List[str] = []
        params: Dict[str, Any] = {}

        if state:
            where_clauses.append("s.state = :state")
            params["state"] = state.upper().strip()

        if search:
            where_clauses.append("(s.seller_id ILIKE :search OR s.city ILIKE :search)")
            params["search"] = f"%{search.strip()}%"

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Count total matching sellers
        count_query = text(f"SELECT COUNT(*) FROM staging.stg_sellers s {where_sql}")
        total_items = db.execute(count_query, params).scalar() or 0

        sort_col = SellerService._ALLOWED_SORT_COLUMNS.get(sort_by, "total_revenue")
        sort_dir = "ASC" if sort_order.lower() == "asc" else "DESC"
        offset = (page - 1) * page_size

        query = text(
            f"""
            SELECT
                s.seller_id,
                s.city,
                s.state,
                s.zip_prefix,
                COUNT(DISTINCT oi.order_id) AS total_orders_fulfilled,
                COUNT(oi.order_item_id) AS total_items_sold,
                COUNT(DISTINCT oi.product_id) AS total_unique_products,
                ROUND(COALESCE(SUM(oi.item_revenue), 0.0)::numeric, 2) AS total_revenue,
                ROUND(COALESCE(AVG(oi.item_revenue), 0.0)::numeric, 2) AS avg_item_value,
                ROUND(COALESCE(AVG(o.delivery_delay_days), 0.0)::numeric, 1) AS avg_delivery_delay_days,
                ROUND(COALESCE(AVG(CASE WHEN o.delivery_delay_days > 0 THEN 1.0 ELSE 0.0 END), 0.0)::numeric * 100.0, 2) AS late_delivery_rate,
                ROUND(COALESCE(AVG(r.review_score), 0.0)::numeric, 2) AS avg_review_score
            FROM staging.stg_sellers s
            JOIN staging.stg_order_items oi ON s.seller_id = oi.seller_id
            JOIN staging.stg_orders o ON oi.order_id = o.order_id
            LEFT JOIN staging.stg_order_reviews r ON o.order_id = r.order_id
            {where_sql}
            GROUP BY s.seller_id, s.city, s.state, s.zip_prefix
            ORDER BY {sort_col} {sort_dir} NULLS LAST
            LIMIT :limit OFFSET :offset
            """
        )
        params["limit"] = page_size
        params["offset"] = offset

        rows = db.execute(query, params).mappings().all()

        items = [
            SellerSummary(
                seller_id=r["seller_id"],
                city=r["city"],
                state=r["state"],
                zip_prefix=r["zip_prefix"],
                total_orders_fulfilled=int(r["total_orders_fulfilled"] or 0),
                total_items_sold=int(r["total_items_sold"] or 0),
                total_unique_products=int(r["total_unique_products"] or 0),
                total_revenue=float(r["total_revenue"] or 0.0),
                avg_item_value=float(r["avg_item_value"] or 0.0),
                avg_delivery_delay_days=(
                    float(r["avg_delivery_delay_days"])
                    if r["avg_delivery_delay_days"] is not None
                    else None
                ),
                late_delivery_rate=float(r["late_delivery_rate"] or 0.0),
                avg_review_score=(
                    float(r["avg_review_score"]) if r["avg_review_score"] is not None else None
                ),
            )
            for r in rows
        ]

        return SellerListResponse(
            items=items,
            pagination=PaginationMeta.create(
                page=page, page_size=page_size, total_items=total_items
            ),
        )

    @staticmethod
    @cached(ttl=300)
    def get_seller_detail(
        db: Session,
        seller_id: str,
        bypass_cache: bool = False,
    ) -> Optional[SellerDetail]:
        """
        Retrieve 360-degree performance profile for a specific seller including top categories.
        """
        query = text(
            """
            SELECT
                s.seller_id,
                s.city,
                s.state,
                s.zip_prefix,
                COUNT(DISTINCT oi.order_id) AS total_orders_fulfilled,
                COUNT(oi.order_item_id) AS total_items_sold,
                COUNT(DISTINCT oi.product_id) AS total_unique_products,
                ROUND(COALESCE(SUM(oi.item_revenue), 0.0)::numeric, 2) AS total_revenue,
                ROUND(COALESCE(AVG(oi.item_revenue), 0.0)::numeric, 2) AS avg_item_value,
                ROUND(COALESCE(AVG(o.delivery_delay_days), 0.0)::numeric, 1) AS avg_delivery_delay_days,
                ROUND(COALESCE(AVG(CASE WHEN o.delivery_delay_days > 0 THEN 1.0 ELSE 0.0 END), 0.0)::numeric * 100.0, 2) AS late_delivery_rate,
                ROUND(COALESCE(AVG(r.review_score), 0.0)::numeric, 2) AS avg_review_score,
                ROUND(COALESCE(AVG(CASE WHEN r.review_score >= 4 THEN 1.0 ELSE 0.0 END), 0.0)::numeric * 100.0, 2) AS positive_reviews_rate
            FROM staging.stg_sellers s
            LEFT JOIN staging.stg_order_items oi ON s.seller_id = oi.seller_id
            LEFT JOIN staging.stg_orders o ON oi.order_id = o.order_id
            LEFT JOIN staging.stg_order_reviews r ON o.order_id = r.order_id
            WHERE s.seller_id = :seller_id
            GROUP BY s.seller_id, s.city, s.state, s.zip_prefix
            """
        )
        row = db.execute(query, {"seller_id": seller_id}).mappings().first()
        if not row:
            return None

        # Top product categories query
        cat_query = text(
            """
            SELECT COALESCE(p.category_name_en, p.category_name_pt, 'other') AS category,
                   COUNT(*) AS items_sold
            FROM staging.stg_order_items oi
            JOIN staging.stg_products p ON oi.product_id = p.product_id
            WHERE oi.seller_id = :seller_id
            GROUP BY 1
            ORDER BY items_sold DESC
            LIMIT 5
            """
        )
        cat_rows = db.execute(cat_query, {"seller_id": seller_id}).mappings().all()
        top_categories = [r["category"] for r in cat_rows if r["category"]]

        return SellerDetail(
            seller_id=row["seller_id"],
            city=row["city"],
            state=row["state"],
            zip_prefix=row["zip_prefix"],
            total_orders_fulfilled=int(row["total_orders_fulfilled"] or 0),
            total_items_sold=int(row["total_items_sold"] or 0),
            total_unique_products=int(row["total_unique_products"] or 0),
            total_revenue=float(row["total_revenue"] or 0.0),
            avg_item_value=float(row["avg_item_value"] or 0.0),
            avg_delivery_delay_days=(
                float(row["avg_delivery_delay_days"])
                if row["avg_delivery_delay_days"] is not None
                else None
            ),
            late_delivery_rate=float(row["late_delivery_rate"] or 0.0),
            avg_review_score=(
                float(row["avg_review_score"]) if row["avg_review_score"] is not None else None
            ),
            top_categories=top_categories,
            recent_orders_count=int(row["total_orders_fulfilled"] or 0),
            positive_reviews_rate=float(row["positive_reviews_rate"] or 0.0),
        )
