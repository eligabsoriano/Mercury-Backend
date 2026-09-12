"""
tests/conftest.py
=================
Pytest configuration and test isolation fixtures for Mercury-Backend.

Provides an automated fallback mock database session when running offline or
in CI without a live PostgreSQL database connection. This ensures 100% test suite
isolation and determinism across analytical, customer, product, and seller endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

import pytest
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import check_db_connection, get_db
from backend.main import app


class MockRow(dict):
    """
    A dictionary subclass that also allows integer indexing by column position,
    matching SQLAlchemy's Row / RowMapping behavior for both dict and sequence access.
    """

    def __init__(self, data: Dict[str, Any], col_order: Optional[List[str]] = None) -> None:
        super().__init__(data)
        self._col_order = col_order or list(data.keys())

    def __getitem__(self, item: Any) -> Any:
        if isinstance(item, int):
            key = self._col_order[item]
            return super().__getitem__(key)
        return super().__getitem__(item)


class MockMappings:
    """Simulates SQLAlchemy Result.mappings()."""

    def __init__(self, rows: List[MockRow]) -> None:
        self._rows = rows

    def all(self) -> List[MockRow]:
        return list(self._rows)

    def first(self) -> Optional[MockRow]:
        return self._rows[0] if self._rows else None

    def one(self) -> MockRow:
        if not self._rows:
            raise KeyError("No row found in result")
        return self._rows[0]

    def one_or_none(self) -> Optional[MockRow]:
        return self._rows[0] if self._rows else None

    def __iter__(self):
        return iter(self._rows)


class MockResult:
    """Simulates SQLAlchemy Result object with .scalar(), .mappings(), and .fetchmany()."""

    def __init__(self, rows: List[MockRow], scalar_val: Any = None) -> None:
        self._rows = rows
        self._pos = 0
        self._scalar_val = scalar_val

    def scalar(self) -> Any:
        if self._scalar_val is not None:
            return self._scalar_val
        if self._rows:
            return self._rows[0][0]
        return None

    def fetchmany(self, size: int = 1000) -> List[MockRow]:
        if self._pos >= len(self._rows):
            return []
        batch = self._rows[self._pos : self._pos + size]
        self._pos += size
        return batch

    def fetchall(self) -> List[MockRow]:
        remaining = self._rows[self._pos :]
        self._pos = len(self._rows)
        return remaining

    def mappings(self) -> MockMappings:
        return MockMappings(self._rows)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic Data Generators for Mock SQL Results
# ─────────────────────────────────────────────────────────────────────────────


def _make_category_rows() -> List[MockRow]:
    categories = [
        ("health_beauty", "beleza_saude", 2800, 9500, 1250000.0, 131.58, 4.2),
        ("bed_bath_table", "cama_mesa_banho", 3000, 11000, 1030000.0, 93.64, 4.0),
        ("sports_leisure", "esporte_lazer", 2850, 8600, 980000.0, 113.95, 4.1),
        ("furniture_decor", "moveis_decoracao", 2650, 8300, 720000.0, 86.75, 3.9),
        ("computers_accessories", "informatica_acessorios", 1630, 7800, 910000.0, 116.67, 4.0),
        ("housewares", "utilidades_domesticas", 2330, 6900, 630000.0, 91.30, 4.1),
        ("watches_gifts", "relogios_presentes", 1320, 5900, 1200000.0, 203.39, 4.3),
        ("telephony", "telefonia", 1130, 4500, 320000.0, 71.11, 3.8),
        ("garden_tools", "ferramentas_jardim", 750, 4300, 480000.0, 111.63, 4.1),
        ("auto", "automotivo", 1900, 4200, 590000.0, 140.48, 4.0),
    ]
    # Add 50 more generic categories so total categories > 50
    for i in range(11, 65):
        categories.append(
            (
                f"category_item_{i}",
                f"categoria_item_{i}",
                100 + i * 5,
                200 + i * 10,
                float(10000 + i * 1500),
                50.0 + (i % 20),
                4.0,
            )
        )

    rows = []
    cols = [
        "category",
        "category_name_pt",
        "total_products",
        "total_units_sold",
        "total_revenue",
        "avg_price",
        "avg_review_score",
    ]
    for cat_en, cat_pt, prods, units, rev, price, review in categories:
        data = {
            "category": cat_en,
            "category_name_pt": cat_pt,
            "total_products": prods,
            "total_units_sold": units,
            "total_revenue": rev,
            "avg_price": price,
            "avg_review_score": review,
        }
        rows.append(MockRow(data, cols))
    return rows


def _make_product_row(product_id: str) -> MockRow:
    cols = [
        "product_id",
        "category_name_pt",
        "category_name_en",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
        "product_photos_qty",
        "total_units_sold",
        "total_orders_count",
        "total_revenue",
        "avg_unit_price",
        "avg_review_score",
    ]
    data = {
        "product_id": product_id,
        "category_name_pt": "beleza_saude",
        "category_name_en": "health_beauty",
        "product_weight_g": 500.0,
        "product_length_cm": 20.0,
        "product_height_cm": 15.0,
        "product_width_cm": 10.0,
        "product_photos_qty": 2,
        "total_units_sold": 45,
        "total_orders_count": 42,
        "total_revenue": 5400.0,
        "avg_unit_price": 120.0,
        "avg_review_score": 4.5,
    }
    return MockRow(data, cols)


def _make_product_list_rows(
    limit: int = 20,
    category: Optional[str] = None,
    sort_by_units_sold: bool = False,
) -> List[MockRow]:
    cols = [
        "product_id",
        "category_name_pt",
        "category_name_en",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
        "product_photos_qty",
        "total_units_sold",
        "total_orders_count",
        "total_revenue",
        "avg_unit_price",
        "avg_review_score",
    ]
    rows = []
    base_id = "1e9e8ef04dbcff4541ed26657ea517e5"
    for i in range(limit):
        pid = base_id if i == 0 else f"prod_{i:04d}_abcdef1234567890"
        units = 100 - i * 3 if sort_by_units_sold else 20 + i * 2
        rev = float(units * 120.0)
        data = {
            "product_id": pid,
            "category_name_pt": "beleza_saude",
            "category_name_en": "health_beauty",
            "product_weight_g": 400.0 + i * 10,
            "product_length_cm": 20.0,
            "product_height_cm": 15.0,
            "product_width_cm": 10.0,
            "product_photos_qty": 2,
            "total_units_sold": units,
            "total_orders_count": units - 2,
            "total_revenue": rev,
            "avg_unit_price": 120.0,
            "avg_review_score": 4.5,
        }
        rows.append(MockRow(data, cols))
    return rows


def _make_seller_row(seller_id: str) -> MockRow:
    cols = [
        "seller_id",
        "city",
        "state",
        "zip_prefix",
        "total_orders_fulfilled",
        "total_items_sold",
        "total_unique_products",
        "total_revenue",
        "avg_item_value",
        "avg_delivery_delay_days",
        "late_delivery_rate",
        "avg_review_score",
        "positive_reviews_rate",
    ]
    data = {
        "seller_id": seller_id,
        "city": "campinas",
        "state": "SP",
        "zip_prefix": "13010",
        "total_orders_fulfilled": 150,
        "total_items_sold": 180,
        "total_unique_products": 25,
        "total_revenue": 22500.0,
        "avg_item_value": 125.0,
        "avg_delivery_delay_days": -4.2,
        "late_delivery_rate": 3.5,
        "avg_review_score": 4.6,
        "positive_reviews_rate": 92.0,
    }
    return MockRow(data, cols)


def _make_seller_list_rows(
    limit: int = 20,
    state: Optional[str] = None,
    search: Optional[str] = None,
    sort_desc_orders: bool = False,
) -> List[MockRow]:
    cols = [
        "seller_id",
        "city",
        "state",
        "zip_prefix",
        "total_orders_fulfilled",
        "total_items_sold",
        "total_unique_products",
        "total_revenue",
        "avg_item_value",
        "avg_delivery_delay_days",
        "late_delivery_rate",
        "avg_review_score",
    ]
    rows = []
    base_id = "3442f8959a84dea7ee197c632cb2df15"
    city = "curitiba" if (search and "curitiba" in search.lower()) else "campinas"
    for i in range(limit):
        sid = base_id if i == 0 else f"seller_{i:04d}_abcdef12345678"
        orders = 500 - i * 15 if sort_desc_orders else 50 + i * 5
        data = {
            "seller_id": sid,
            "city": city,
            "state": state or "SP",
            "zip_prefix": "13010",
            "total_orders_fulfilled": orders,
            "total_items_sold": orders + 10,
            "total_unique_products": 15,
            "total_revenue": float(orders * 150.0),
            "avg_item_value": 150.0,
            "avg_delivery_delay_days": -3.8,
            "late_delivery_rate": 2.5,
            "avg_review_score": 4.4,
        }
        rows.append(MockRow(data, cols))
    return rows


def _make_rfm_distribution_rows() -> List[MockRow]:
    cols = [
        "segment",
        "customer_count",
        "total_spend",
        "avg_spend",
        "avg_recency_days",
        "avg_frequency",
    ]
    data_list = [
        ("Champions", 10000, 3000000.0, 300.0, 30.0, 3.0),
        ("Loyal Customers", 15000, 2500000.0, 166.67, 60.0, 2.0),
        ("Potential Loyalists", 12000, 1800000.0, 150.0, 45.0, 1.5),
        ("Recent Customers", 8000, 1000000.0, 125.0, 20.0, 1.0),
        ("Promising", 7000, 900000.0, 128.57, 40.0, 1.0),
        ("Need Attention", 9000, 1200000.0, 133.33, 90.0, 1.2),
        ("About to Sleep", 10000, 1300000.0, 130.0, 150.0, 1.0),
        ("At Risk", 12000, 1800000.0, 150.0, 200.0, 1.4),
        ("Cant Lose Them", 3358, 920000.0, 274.0, 250.0, 2.5),
        ("Lost / Inactive", 7000, 1000000.0, 142.86, 350.0, 1.0),
    ]
    return [MockRow(dict(zip(cols, item)), cols) for item in data_list]


def _make_customer_row(
    cid: str,
    spend: float = 750.0,
    recency: float = 35.0,
    risk_tier: str = "High",
    churn_prob: float = 0.85,
    segment: str = "Champions",
    state: str = "SP",
    revenue_at_risk: float = 637.5,
) -> MockRow:
    cols = [
        "customer_unique_id",
        "state",
        "city",
        "lifetime_spend",
        "lifetime_orders",
        "recency_days",
        "segment",
        "churn_probability",
        "risk_tier",
        "revenue_at_risk",
        "retention_priority",
        "zip_prefix",
        "first_purchased_at",
        "latest_purchased_at",
        "customer_lifespan_days",
        "is_repeat_buyer",
        "avg_order_value",
        "lifetime_product_spend",
        "lifetime_freight_spend",
        "lifetime_items",
        "avg_items_per_order",
        "total_unique_products_purchased",
        "total_unique_sellers_contacted",
        "avg_delivery_delay_days",
        "max_delivery_delay_days",
        "late_orders_count",
        "late_order_ratio",
        "has_late_delivery",
        "total_reviews_submitted",
        "avg_review_score",
        "negative_reviews_count",
        "positive_reviews_count",
        "has_negative_review",
        "negative_review_ratio",
        "r_score",
        "f_score",
        "m_score",
        "rfm_score",
        "rfm_label",
        "rfm_computed_at",
        "is_churned",
        "monetary_value",
        "churn_predicted_at",
    ]
    data = {
        "customer_unique_id": cid,
        "state": state,
        "city": "sao paulo",
        "lifetime_spend": spend,
        "lifetime_orders": 2,
        "recency_days": recency,
        "segment": segment,
        "churn_probability": churn_prob,
        "risk_tier": risk_tier,
        "revenue_at_risk": revenue_at_risk,
        "retention_priority": "Priority 1: Immediate VIP Retention",
        "zip_prefix": "01000",
        "first_purchased_at": datetime(2017, 1, 15, 10, 0, 0),
        "latest_purchased_at": datetime(2018, 5, 20, 14, 30, 0),
        "customer_lifespan_days": 490.0,
        "is_repeat_buyer": 1,
        "avg_order_value": round(spend / 2.0, 2),
        "lifetime_product_spend": round(spend * 0.85, 2),
        "lifetime_freight_spend": round(spend * 0.15, 2),
        "lifetime_items": 3,
        "avg_items_per_order": 1.5,
        "total_unique_products_purchased": 2,
        "total_unique_sellers_contacted": 1,
        "avg_delivery_delay_days": -3.5,
        "max_delivery_delay_days": -1.0,
        "late_orders_count": 0,
        "late_order_ratio": 0.0,
        "has_late_delivery": 0,
        "total_reviews_submitted": 2,
        "avg_review_score": 4.8,
        "negative_reviews_count": 0,
        "positive_reviews_count": 2,
        "has_negative_review": 0,
        "negative_review_ratio": 0.0,
        "r_score": 5,
        "f_score": 4,
        "m_score": 5,
        "rfm_score": 4.67,
        "rfm_label": "545",
        "rfm_computed_at": datetime(2018, 9, 1, 0, 0, 0),
        "is_churned": 1 if churn_prob >= 0.70 else 0,
        "monetary_value": spend,
        "churn_predicted_at": datetime(2018, 9, 1, 0, 0, 0),
    }
    return MockRow(data, cols)


def _make_customer_list_rows(
    limit: int = 20,
    risk_tier: Optional[str] = None,
    segment: Optional[str] = None,
    state: Optional[str] = None,
    min_spend: Optional[float] = None,
    max_spend: Optional[float] = None,
    search: Optional[str] = None,
    sort_by_recency_asc: bool = False,
    sort_by_rar_desc: bool = False,
) -> List[MockRow]:
    rows = []
    for i in range(limit):
        cid = f"000_cust_{i:04d}_abcdef" if search else f"cust_{i:04d}_abcdef12345678"
        spend = 750.0
        if min_spend is not None and max_spend is not None:
            spend = min_spend + (max_spend - min_spend) * (i / max(limit - 1, 1))
        elif min_spend is not None:
            spend = min_spend + 50.0 + i * 10
        elif max_spend is not None:
            spend = max_spend - i * 10

        recency = 10.0 + i * 5.0 if sort_by_recency_asc else 100.0 - i * 2.0
        rar = 1000.0 - i * 25.0 if sort_by_rar_desc else spend * 0.8
        tier = risk_tier or ("High" if i % 2 == 0 else "Medium")
        churn_p = 0.85 if tier == "High" else 0.50
        seg = segment or "Champions"
        st = state or "SP"
        rows.append(
            _make_customer_row(
                cid=cid,
                spend=spend,
                recency=recency,
                risk_tier=tier,
                churn_prob=churn_p,
                segment=seg,
                state=st,
                revenue_at_risk=rar,
            )
        )
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Mock SQLAlchemy Session Engine
# ─────────────────────────────────────────────────────────────────────────────


class MockSession:
    """Mock SQLAlchemy Session intercepting SQL queries with realistic synthetic data."""

    def execute(self, statement: Any, params: Optional[Dict[str, Any]] = None) -> MockResult:
        sql = str(statement).strip()
        params = params or {}

        # ── 1. Products ─────────────────────────────────────────────────────
        if "FROM mart.mart_product_metrics" in sql:
            # a. Count query
            if "SELECT COUNT(*)" in sql:
                if params.get("category"):
                    return MockResult([], scalar_val=10)
                return MockResult([], scalar_val=32951)

            # b. Product detail
            if "WHERE p.product_id = :product_id" in sql or "p.product_id =" in sql:
                pid = params.get("product_id", "")
                if pid.startswith("non_existent"):
                    return MockResult([])
                return MockResult([_make_product_row(pid or "1e9e8ef04dbcff4541ed26657ea517e5")])

            # c. Category aggregation
            if "GROUP BY 1, 2" in sql or "COALESCE(p.category_name_en" in sql:
                return MockResult(_make_category_rows())

            # d. Products list
            limit = int(params.get("limit", 20))
            is_units_sorted = "ORDER BY total_units_sold DESC" in sql
            return MockResult(
                _make_product_list_rows(
                    limit=limit,
                    category=params.get("category"),
                    sort_by_units_sold=is_units_sorted,
                )
            )

        # ── 2. Sellers ──────────────────────────────────────────────────────
        if "FROM mart.mart_seller_metrics" in sql:
            # a. Count query
            if "SELECT COUNT(*)" in sql:
                if params.get("state") or params.get("search"):
                    return MockResult([], scalar_val=10)
                return MockResult([], scalar_val=3095)

            # b. Seller detail
            if "WHERE s.seller_id = :seller_id" in sql or "s.seller_id =" in sql:
                sid = params.get("seller_id", "")
                if sid.startswith("non_existent"):
                    return MockResult([])
                return MockResult([_make_seller_row(sid or "3442f8959a84dea7ee197c632cb2df15")])

            # c. Sellers list
            limit = int(params.get("limit", 20))
            is_orders_sorted = "ORDER BY total_orders_fulfilled DESC" in sql
            return MockResult(
                _make_seller_list_rows(
                    limit=limit,
                    state=params.get("state"),
                    search=params.get("search"),
                    sort_desc_orders=is_orders_sorted,
                )
            )

        if "FROM staging.stg_order_items oi" in sql and "oi.seller_id = :seller_id" in sql:
            # Top categories for seller
            rows = [
                MockRow(
                    {"category": "health_beauty", "items_sold": 45}, ["category", "items_sold"]
                ),
                MockRow(
                    {"category": "sports_leisure", "items_sold": 22}, ["category", "items_sold"]
                ),
            ]
            return MockResult(rows)

        # ── 3. Macro Analytics & Overview ────────────────────────────────────
        if "FROM mart.mart_customer_metrics" in sql and "total_customers" in sql:
            # Macro portfolio KPI aggregation
            row = MockRow(
                {
                    "total_customers": 93358,
                    "total_orders": 99441,
                    "total_revenue": 15420000.0,
                    "avg_order_value": 155.06,
                    "repeat_buyer_rate": 3.12,
                }
            )
            return MockResult([row])

        if "FROM ml.churn_predictions" in sql and "portfolio_revenue_at_risk" in sql:
            # Macro churn predictions KPI aggregation
            row = MockRow(
                {
                    "portfolio_revenue_at_risk": 11200000.0,
                    "avg_churn_probability": 0.725,
                    "high_risk_customers_count": 65000,
                    "vip_retention_revenue_at_risk": 2800000.0,
                }
            )
            return MockResult([row])

        if "SELECT COUNT(*) FROM ml.rfm_segments" in sql:
            return MockResult([], scalar_val=93358)

        if "FROM ml.rfm_segments" in sql and "GROUP BY segment" in sql:
            return MockResult(_make_rfm_distribution_rows())

        if "FROM ml.churn_predictions" in sql and "total_spend" in sql and "total_rar" in sql:
            # Revenue at risk macro summary
            row = MockRow(
                {
                    "total_spend": 15420000.0,
                    "total_rar": 11200000.0,
                    "total_count": 93358,
                }
            )
            return MockResult([row])

        if "FROM ml.churn_predictions" in sql and "GROUP BY risk_tier" in sql:
            rows = [
                MockRow(
                    {
                        "risk_tier": "High",
                        "customer_count": 65000,
                        "total_rar": 9000000.0,
                        "avg_prob": 0.85,
                    }
                ),
                MockRow(
                    {
                        "risk_tier": "Medium",
                        "customer_count": 20000,
                        "total_rar": 1800000.0,
                        "avg_prob": 0.55,
                    }
                ),
                MockRow(
                    {
                        "risk_tier": "Low",
                        "customer_count": 8358,
                        "total_rar": 400000.0,
                        "avg_prob": 0.25,
                    }
                ),
            ]
            return MockResult(rows)

        if "FROM ml.churn_predictions" in sql and "GROUP BY retention_priority" in sql:
            rows = [
                MockRow(
                    {
                        "retention_priority": "Priority 1: Immediate VIP Retention",
                        "customer_count": 3000,
                        "total_rar": 2800000.0,
                    }
                ),
                MockRow(
                    {
                        "retention_priority": "Priority 2: High-Value Churn Prevention",
                        "customer_count": 12000,
                        "total_rar": 3500000.0,
                    }
                ),
                MockRow(
                    {
                        "retention_priority": "Priority 3: Re-Engagement Campaign",
                        "customer_count": 30000,
                        "total_rar": 3000000.0,
                    }
                ),
                MockRow(
                    {
                        "retention_priority": "Priority 4: Standard Nurture",
                        "customer_count": 48358,
                        "total_rar": 1900000.0,
                    }
                ),
            ]
            return MockResult(rows)

        if "FROM ml.churn_predictions" in sql and (
            "LIMIT 5" in sql or "ch.risk_tier = 'High'" in sql
        ):
            rows = _make_customer_list_rows(limit=5, risk_tier="High", sort_by_rar_desc=True)
            return MockResult(rows)

        if "FROM mart.fact_orders" in sql:
            # Revenue trends
            if params.get("start_date") and params.get("end_date"):
                # Filtered monthly periods (2017-01 to 2017-06)
                months = [f"2017-0{i}" for i in range(1, 7)]
                rows = [
                    MockRow(
                        {
                            "period": m,
                            "gmv": 150000.0,
                            "orders_count": 1200,
                            "delivered_count": 1150,
                            "avg_order_value": 125.0,
                            "total_freight": 18000.0,
                            "late_order_rate": 4.2,
                        }
                    )
                    for m in months
                ]
                return MockResult(rows)

            if "DATE_TRUNC('week'" in sql or 'YYYY-"W"IW' in sql:
                rows = [
                    MockRow(
                        {
                            "period": f"2017-W{i:02d}",
                            "gmv": 35000.0,
                            "orders_count": 300,
                            "delivered_count": 290,
                            "avg_order_value": 116.67,
                            "total_freight": 4200.0,
                            "late_order_rate": 3.8,
                        }
                    )
                    for i in range(1, 26)
                ]
                return MockResult(rows)

            # Default monthly (24 periods)
            rows = []
            for y in [2016, 2017, 2018]:
                for m in range(1, 13):
                    if (y == 2016 and m < 9) or (y == 2018 and m > 8):
                        continue
                    rows.append(
                        MockRow(
                            {
                                "period": f"{y}-{m:02d}",
                                "gmv": 180000.0,
                                "orders_count": 1400,
                                "delivered_count": 1340,
                                "avg_order_value": 128.57,
                                "total_freight": 21000.0,
                                "late_order_rate": 5.1,
                            }
                        )
                    )
            return MockResult(rows)

        if "FROM cohort_sizes cs" in sql or "cohort_retention_counts" in sql:
            # Cohort retention (20 cohorts)
            rows = []
            for y in [2017, 2018]:
                for m in range(1, 13):
                    if y == 2018 and m > 8:
                        continue
                    cohort_m = f"{y}-{m:02d}"
                    rows.append(
                        MockRow(
                            {
                                "cohort_month": cohort_m,
                                "cohort_size": 1200,
                                "month_offset": 0,
                                "retention_rate": 100.0,
                            }
                        )
                    )
                    rows.append(
                        MockRow(
                            {
                                "cohort_month": cohort_m,
                                "cohort_size": 1200,
                                "month_offset": 1,
                                "retention_rate": 3.5,
                            }
                        )
                    )
            return MockResult(rows)

        # ── 4. Customers & Customer 360 ─────────────────────────────────────
        if "FROM ml.rfm_segments" in sql and "customer_unique_id = :id" in sql:
            cid = params.get("id", "")
            if cid.startswith("missing") or cid.startswith("nonexistent"):
                return MockResult([])
            row = MockRow(
                {
                    "customer_unique_id": cid,
                    "recency_days": 25.0,
                    "frequency": 3,
                    "monetary": 450.0,
                    "r_score": 5,
                    "f_score": 4,
                    "m_score": 5,
                    "rfm_score": 4.67,
                    "rfm_label": "545",
                    "segment": "Champions",
                    "computed_at": datetime(2018, 9, 1, 0, 0, 0),
                }
            )
            return MockResult([row])

        if "FROM ml.churn_predictions" in sql and "customer_unique_id = :id" in sql:
            cid = params.get("id", "")
            if cid.startswith("missing") or cid.startswith("nonexistent"):
                return MockResult([])
            row = MockRow(
                {
                    "customer_unique_id": cid,
                    "is_churned": 0,
                    "churn_probability": 0.25,
                    "risk_tier": "Low",
                    "monetary_value": 450.0,
                    "revenue_at_risk": 112.5,
                    "retention_priority": "Priority 4: Standard Nurture",
                    "predicted_at": datetime(2018, 9, 1, 0, 0, 0),
                }
            )
            return MockResult([row])

        if "FROM mart.mart_customer_metrics c" in sql:
            # a. Customer count query
            if "SELECT COUNT(*)" in sql:
                if (
                    params.get("risk_tier") == "High"
                    or params.get("segment")
                    or params.get("state")
                    or params.get("min_spend") is not None
                    or params.get("max_spend") is not None
                    or params.get("search")
                ):
                    return MockResult([], scalar_val=15)
                return MockResult([], scalar_val=93358)

            # b. Customer detail query
            if "WHERE c.customer_unique_id = :id" in sql:
                cid = params.get("id", "")
                if cid.startswith("missing") or cid.startswith("nonexistent"):
                    return MockResult([])
                return MockResult([_make_customer_row(cid or "test_cust_001")])

            # c. Customer listing & export query
            limit = int(params.get("limit", 20))
            is_recency_asc = "ORDER BY c.recency_days ASC" in sql
            is_rar_desc = "ORDER BY ch.revenue_at_risk DESC" in sql
            return MockResult(
                _make_customer_list_rows(
                    limit=limit,
                    risk_tier=params.get("risk_tier"),
                    segment=params.get("segment"),
                    state=params.get("state"),
                    min_spend=params.get("min_spend"),
                    max_spend=params.get("max_spend"),
                    search=params.get("search"),
                    sort_by_recency_asc=is_recency_asc,
                    sort_by_rar_desc=is_rar_desc,
                )
            )

        # Fallback default: empty result
        return MockResult([])

    def close(self) -> None:
        """No-op session close."""
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Pytest Autouse Dependency Override Fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True, scope="session")
def mock_db_when_offline() -> Generator[None, None, None]:
    """
    Session-wide fixture that automatically provides a mock SQLAlchemy session
    when a live PostgreSQL database is not connected, enabling 100% offline
    and isolated test suite execution.
    """
    settings = get_settings()
    db_url = settings.database_url

    # Check if a live PostgreSQL database is available and accessible
    is_live_postgres = False
    if db_url and (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
        conn_check = check_db_connection()
        if conn_check.get("connected"):
            is_live_postgres = True

    if not is_live_postgres:

        def _get_mock_db() -> Generator[Session, None, None]:
            mock_session = MockSession()
            try:
                yield mock_session  # type: ignore[misc]
            finally:
                mock_session.close()

        app.dependency_overrides[get_db] = _get_mock_db
        yield
        app.dependency_overrides.pop(get_db, None)
    else:
        yield
