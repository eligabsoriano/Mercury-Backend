"""
backend/services/product_service.py
===================================
Database service for product catalog analytics, sales velocity, and category breakdowns.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.cache import cached
from backend.schemas.common import PaginationMeta
from backend.schemas.product import (
    CategoryListResponse,
    CategorySummary,
    ProductListResponse,
    ProductSummary,
)

log = logging.getLogger(__name__)


class ProductService:
    """Service providing product catalog and category intelligence."""

    _ALLOWED_SORT_COLUMNS = {
        "total_revenue": "total_revenue",
        "total_units_sold": "total_units_sold",
        "total_orders_count": "total_orders_count",
        "avg_unit_price": "avg_unit_price",
        "avg_review_score": "avg_review_score",
    }

    @staticmethod
    @cached(ttl=300)
    def get_products(
        db: Session,
        page: int = 1,
        page_size: int = 20,
        category: Optional[str] = None,
        sort_by: str = "total_revenue",
        sort_order: str = "desc",
        search: Optional[str] = None,
        bypass_cache: bool = False,
    ) -> ProductListResponse:
        """
        Fetch paginated product catalog with sales velocity, revenue, and customer review scores.
        """
        where_clauses: List[str] = []
        params: Dict[str, Any] = {}

        if category:
            where_clauses.append(
                "(p.category_name_en ILIKE :category OR p.category_name_pt ILIKE :category)"
            )
            params["category"] = f"%{category.strip()}%"

        if search:
            where_clauses.append(
                "(p.product_id ILIKE :search OR p.category_name_en ILIKE :search OR p.category_name_pt ILIKE :search)"
            )
            params["search"] = f"%{search.strip()}%"

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        count_query = text(f"SELECT COUNT(*) FROM staging.stg_products p {where_sql}")
        total_items = db.execute(count_query, params).scalar() or 0

        sort_col = ProductService._ALLOWED_SORT_COLUMNS.get(sort_by, "total_revenue")
        sort_dir = "ASC" if sort_order.lower() == "asc" else "DESC"
        offset = (page - 1) * page_size

        query = text(
            f"""
            SELECT
                p.product_id,
                p.category_name_pt,
                p.category_name_en,
                p.product_weight_g,
                p.product_length_cm,
                p.product_height_cm,
                p.product_width_cm,
                p.product_photos_qty,
                COUNT(oi.order_item_id) AS total_units_sold,
                COUNT(DISTINCT oi.order_id) AS total_orders_count,
                ROUND(COALESCE(SUM(oi.item_revenue), 0.0)::numeric, 2) AS total_revenue,
                ROUND(COALESCE(AVG(oi.price), 0.0)::numeric, 2) AS avg_unit_price,
                ROUND(COALESCE(AVG(r.review_score), 0.0)::numeric, 2) AS avg_review_score
            FROM staging.stg_products p
            LEFT JOIN staging.stg_order_items oi ON p.product_id = oi.product_id
            LEFT JOIN staging.stg_order_reviews r ON oi.order_id = r.order_id
            {where_sql}
            GROUP BY
                p.product_id,
                p.category_name_pt,
                p.category_name_en,
                p.product_weight_g,
                p.product_length_cm,
                p.product_height_cm,
                p.product_width_cm,
                p.product_photos_qty
            ORDER BY {sort_col} {sort_dir} NULLS LAST
            LIMIT :limit OFFSET :offset
            """
        )
        params["limit"] = page_size
        params["offset"] = offset

        rows = db.execute(query, params).mappings().all()

        items = [
            ProductSummary(
                product_id=r["product_id"],
                category_name_pt=r["category_name_pt"],
                category_name_en=r["category_name_en"],
                total_units_sold=int(r["total_units_sold"] or 0),
                total_orders_count=int(r["total_orders_count"] or 0),
                total_revenue=float(r["total_revenue"] or 0.0),
                avg_unit_price=float(r["avg_unit_price"] or 0.0),
                avg_review_score=float(r["avg_review_score"])
                if r["avg_review_score"] is not None
                else None,
                product_weight_g=float(r["product_weight_g"])
                if r["product_weight_g"] is not None
                else None,
                product_length_cm=float(r["product_length_cm"])
                if r["product_length_cm"] is not None
                else None,
                product_height_cm=float(r["product_height_cm"])
                if r["product_height_cm"] is not None
                else None,
                product_width_cm=float(r["product_width_cm"])
                if r["product_width_cm"] is not None
                else None,
                product_photos_qty=int(r["product_photos_qty"])
                if r["product_photos_qty"] is not None
                else None,
            )
            for r in rows
        ]

        return ProductListResponse(
            items=items,
            pagination=PaginationMeta.create(
                page=page, page_size=page_size, total_items=total_items
            ),
        )

    @staticmethod
    @cached(ttl=300)
    def get_categories(
        db: Session,
        bypass_cache: bool = False,
    ) -> CategoryListResponse:
        """
        Aggregate category performance summary including unit sales, revenue, and average review scores.
        """
        query = text(
            """
            SELECT
                COALESCE(p.category_name_en, p.category_name_pt, 'uncategorized') AS category,
                p.category_name_pt,
                COUNT(DISTINCT p.product_id) AS total_products,
                COUNT(oi.order_item_id) AS total_units_sold,
                ROUND(COALESCE(SUM(oi.item_revenue), 0.0)::numeric, 2) AS total_revenue,
                ROUND(COALESCE(AVG(oi.price), 0.0)::numeric, 2) AS avg_price,
                ROUND(COALESCE(AVG(r.review_score), 0.0)::numeric, 2) AS avg_review_score
            FROM staging.stg_products p
            JOIN staging.stg_order_items oi ON p.product_id = oi.product_id
            LEFT JOIN staging.stg_order_reviews r ON oi.order_id = r.order_id
            GROUP BY 1, 2
            ORDER BY total_revenue DESC
            """
        )
        rows = db.execute(query).mappings().all()

        categories = [
            CategorySummary(
                category=r["category"],
                category_pt=r["category_name_pt"],
                total_products=int(r["total_products"]),
                total_units_sold=int(r["total_units_sold"]),
                total_revenue=float(r["total_revenue"]),
                avg_price=float(r["avg_price"]),
                avg_review_score=float(r["avg_review_score"])
                if r["avg_review_score"] is not None
                else None,
            )
            for r in rows
        ]

        return CategoryListResponse(
            total_categories=len(categories),
            categories=categories,
        )

    @staticmethod
    @cached(ttl=300)
    def get_product_detail(
        db: Session,
        product_id: str,
        bypass_cache: bool = False,
    ) -> Optional[ProductSummary]:
        """
        Retrieve performance scorecard for an individual product.
        """
        query = text(
            """
            SELECT
                p.product_id,
                p.category_name_pt,
                p.category_name_en,
                p.product_weight_g,
                p.product_length_cm,
                p.product_height_cm,
                p.product_width_cm,
                p.product_photos_qty,
                COUNT(oi.order_item_id) AS total_units_sold,
                COUNT(DISTINCT oi.order_id) AS total_orders_count,
                ROUND(COALESCE(SUM(oi.item_revenue), 0.0)::numeric, 2) AS total_revenue,
                ROUND(COALESCE(AVG(oi.price), 0.0)::numeric, 2) AS avg_unit_price,
                ROUND(COALESCE(AVG(r.review_score), 0.0)::numeric, 2) AS avg_review_score
            FROM staging.stg_products p
            LEFT JOIN staging.stg_order_items oi ON p.product_id = oi.product_id
            LEFT JOIN staging.stg_order_reviews r ON oi.order_id = r.order_id
            WHERE p.product_id = :product_id
            GROUP BY
                p.product_id,
                p.category_name_pt,
                p.category_name_en,
                p.product_weight_g,
                p.product_length_cm,
                p.product_height_cm,
                p.product_width_cm,
                p.product_photos_qty
            """
        )
        row = db.execute(query, {"product_id": product_id}).mappings().first()
        if not row:
            return None

        return ProductSummary(
            product_id=row["product_id"],
            category_name_pt=row["category_name_pt"],
            category_name_en=row["category_name_en"],
            total_units_sold=int(row["total_units_sold"] or 0),
            total_orders_count=int(row["total_orders_count"] or 0),
            total_revenue=float(row["total_revenue"] or 0.0),
            avg_unit_price=float(row["avg_unit_price"] or 0.0),
            avg_review_score=float(row["avg_review_score"])
            if row["avg_review_score"] is not None
            else None,
            product_weight_g=float(row["product_weight_g"])
            if row["product_weight_g"] is not None
            else None,
            product_length_cm=float(row["product_length_cm"])
            if row["product_length_cm"] is not None
            else None,
            product_height_cm=float(row["product_height_cm"])
            if row["product_height_cm"] is not None
            else None,
            product_width_cm=float(row["product_width_cm"])
            if row["product_width_cm"] is not None
            else None,
            product_photos_qty=int(row["product_photos_qty"])
            if row["product_photos_qty"] is not None
            else None,
        )
