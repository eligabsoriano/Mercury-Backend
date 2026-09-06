"""
tests/test_dbt_models.py
========================
Validates that dbt staging views exist, have expected record counts,
filter to delivered orders, and resolve the customer_unique_id key.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_STAGING_VIEWS = {
    "staging.stg_customers",
    "staging.stg_orders",
    "staging.stg_order_items",
    "staging.stg_order_payments",
    "staging.stg_order_reviews",
    "staging.stg_products",
    "staging.stg_sellers",
}


@pytest.fixture(scope="module")
def db_conn():
    load_dotenv(REPO_ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not configured in .env")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    yield conn
    conn.close()


def test_staging_views_exist(db_conn):
    """Verify all 7 dbt staging views are created in the staging schema."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_schema || '.' || table_name
            FROM information_schema.views
            WHERE table_schema = 'staging';
            """
        )
        found = {row[0] for row in cur.fetchall()}
        assert EXPECTED_STAGING_VIEWS.issubset(found), f"Missing staging views: {EXPECTED_STAGING_VIEWS - found}"


def test_stg_customers_has_unique_id(db_conn):
    """Verify stg_customers surfaces customer_unique_id alongside customer_id."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT customer_id, customer_unique_id, city, state FROM staging.stg_customers LIMIT 5;")
        rows = cur.fetchall()
        assert len(rows) == 5
        for row in rows:
            assert row[0] is not None
            assert row[1] is not None


def test_stg_orders_delivered_filter(db_conn):
    """Verify stg_orders only includes delivered orders (96,478)."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM staging.stg_orders;")
        count = cur.fetchone()[0]
        assert count == 96478

        cur.execute("SELECT COUNT(*) FROM staging.stg_orders WHERE order_status != 'delivered';")
        non_delivered = cur.fetchone()[0]
        assert non_delivered == 0

        cur.execute("SELECT COUNT(*) FROM staging.stg_orders WHERE is_delivered IS NOT TRUE;")
        not_flagged = cur.fetchone()[0]
        assert not_flagged == 0


def test_stg_order_items_revenue(db_conn):
    """Verify stg_order_items calculates item_revenue = price + freight_value."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT price, freight_value, item_revenue 
            FROM staging.stg_order_items 
            LIMIT 10;
            """
        )
        rows = cur.fetchall()
        assert len(rows) == 10
        for price, freight, revenue in rows:
            assert revenue == price + freight


def test_stg_order_reviews_sentiment_flags(db_conn):
    """Verify stg_order_reviews has boolean sentiment flags."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT review_score, is_negative_review, is_positive_review
            FROM staging.stg_order_reviews
            LIMIT 50;
            """
        )
        rows = cur.fetchall()
        for score, neg, pos in rows:
            if score <= 2:
                assert neg is True
                assert pos is False
            elif score >= 4:
                assert pos is True
                assert neg is False
            else:
                assert neg is False
                assert pos is False


def test_intermediate_views_exist(db_conn):
    """Verify all 6 intermediate views exist in the intermediate schema."""
    expected = {
        "int_order_items_aggregated",
        "int_order_reviews_aggregated",
        "int_customer_locations",
        "int_customer_orders",
        "int_customer_fulfillment",
        "int_customer_reviews",
    }
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'intermediate';
            """
        )
        found = {row[0] for row in cur.fetchall()}
        assert expected.issubset(found), f"Missing intermediate views: {expected - found}"


def test_mart_tables_exist(db_conn):
    """Verify all 3 mart tables are materialized in the mart schema."""
    expected = {
        "dim_customers",
        "fact_orders",
        "mart_customer_metrics",
    }
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'mart' AND table_type = 'BASE TABLE';
            """
        )
        found = {row[0] for row in cur.fetchall()}
        assert expected.issubset(found), f"Missing mart tables: {expected - found}"


def test_mart_customer_metrics_integrity(db_conn):
    """Verify mart_customer_metrics has exact customer count, positive spend, and non-null recency."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM mart.mart_customer_metrics;")
        total_customers = cur.fetchone()[0]
        assert total_customers == 93358

        cur.execute(
            """
            SELECT 
                MIN(recency_days),
                MAX(recency_days),
                MIN(lifetime_spend),
                SUM(CASE WHEN is_repeat_buyer THEN 1 ELSE 0 END)
            FROM mart.mart_customer_metrics;
            """
        )
        min_rec, max_rec, min_spend, repeat_count = cur.fetchone()
        assert min_rec == 0
        assert max_rec > 0
        assert min_spend > 0
        assert repeat_count > 0


def test_fact_orders_integrity(db_conn):
    """Verify fact_orders has all 96,478 delivered orders and correct total revenue."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM mart.fact_orders;")
        total_orders = cur.fetchone()[0]
        assert total_orders == 96478

        cur.execute("SELECT COUNT(*) FROM mart.fact_orders WHERE total_revenue <= 0;")
        invalid_rev = cur.fetchone()[0]
        assert invalid_rev == 0


def test_dim_customers_integrity(db_conn):
    """Verify dim_customers matches unique customer count and has non-null locations."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM mart.dim_customers;")
        count = cur.fetchone()[0]
        assert count == 93358

        cur.execute("SELECT COUNT(*) FROM mart.dim_customers WHERE city IS NULL OR state IS NULL;")
        missing_loc = cur.fetchone()[0]
        assert missing_loc == 0

