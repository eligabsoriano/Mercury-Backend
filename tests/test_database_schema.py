"""
tests/test_database_schema.py
=============================
Validates that PostgreSQL schemas, tables, constraints, and views
match the architecture specifications in Neon.
"""

from __future__ import annotations

import os
import psycopg2
import pytest
from dotenv import load_dotenv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_SCHEMAS = {"raw", "raw_marketing", "staging"}

EXPECTED_RAW_TABLES = {
    "raw.category_translations",
    "raw.customers",
    "raw.geolocation",
    "raw.order_items",
    "raw.order_payments",
    "raw.order_reviews",
    "raw.orders",
    "raw.products",
    "raw.sellers",
    "raw_marketing.closed_deals",
    "raw_marketing.mql",
}

EXPECTED_RAW_VIEWS = {
    "raw.vw_delivered_orders",
    "raw.vw_order_revenue",
    "raw.vw_ingestion_summary",
}


@pytest.fixture(scope="module")
def db_conn():
    load_dotenv(REPO_ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not configured in .env")
    conn = psycopg2.connect(url)
    yield conn
    conn.close()


def test_database_connection(db_conn):
    """Test that connection to PostgreSQL succeeds and server is responsive."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT 1;")
        result = cur.fetchone()
        assert result == (1,)


def test_schemas_exist(db_conn):
    """Verify that all architectural schemas exist."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name IN ('raw', 'raw_marketing', 'staging');
            """
        )
        found = {row[0] for row in cur.fetchall()}
        assert EXPECTED_SCHEMAS.issubset(found), f"Missing schemas: {EXPECTED_SCHEMAS - found}"


def test_raw_tables_exist(db_conn):
    """Verify that all 11 raw tables are present."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_schema || '.' || table_name 
            FROM information_schema.tables 
            WHERE table_schema IN ('raw', 'raw_marketing')
              AND table_type = 'BASE TABLE';
            """
        )
        found = {row[0] for row in cur.fetchall()}
        assert EXPECTED_RAW_TABLES.issubset(found), f"Missing tables: {EXPECTED_RAW_TABLES - found}"


def test_raw_views_exist(db_conn):
    """Verify that helper views exist."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_schema || '.' || table_name 
            FROM information_schema.views 
            WHERE table_schema = 'raw';
            """
        )
        found = {row[0] for row in cur.fetchall()}
        assert EXPECTED_RAW_VIEWS.issubset(found), f"Missing views: {EXPECTED_RAW_VIEWS - found}"


def test_order_reviews_compound_primary_key(db_conn):
    """Verify raw.order_reviews has compound primary key (review_id, order_id)."""
    with db_conn.cursor() as cur:
        cur.execute(
            """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.table_schema = 'raw'
              AND tc.table_name = 'order_reviews'
              AND tc.constraint_type = 'PRIMARY KEY'
            ORDER BY kcu.ordinal_position;
            """
        )
        pk_cols = [row[0] for row in cur.fetchall()]
        assert pk_cols == ["review_id", "order_id"], f"Expected PK ['review_id', 'order_id'], got {pk_cols}"
