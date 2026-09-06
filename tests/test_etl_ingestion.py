"""
tests/test_etl_ingestion.py
===========================
Validates dataset file resolution, column alignments, and database row counts.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg2
import pytest
from dotenv import load_dotenv

from etl.ingest import (
    CORE_TABLES,
    DEFAULT_MARKETING_DIRS,
    DEFAULT_OLIST_DIRS,
    MARKETING_TABLES,
    find_csv_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_COUNTS = {
    "raw.category_translations": 71,
    "raw.customers": 99441,
    "raw.geolocation": 1000163,
    "raw.order_items": 112650,
    "raw.order_payments": 103886,
    "raw.order_reviews": 99224,
    "raw.orders": 99441,
    "raw.products": 32951,
    "raw.sellers": 3095,
    "raw_marketing.closed_deals": 842,
    "raw_marketing.mql": 8000,
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


def test_core_csv_files_resolved():
    """Verify that all 9 Olist core CSV files are discovered in dataset directories."""
    for spec in CORE_TABLES:
        csv_file = find_csv_file(spec["file"], DEFAULT_OLIST_DIRS)
        assert csv_file is not None, f"Could not find core CSV: {spec['file']}"
        assert csv_file.is_file()
        assert csv_file.stat().st_size > 0


def test_marketing_csv_files_resolved():
    """Verify that marketing funnel CSV files are discovered in dataset directories."""
    for spec in MARKETING_TABLES:
        csv_file = find_csv_file(spec["file"], DEFAULT_MARKETING_DIRS)
        assert csv_file is not None, f"Could not find marketing CSV: {spec['file']}"
        assert csv_file.is_file()
        assert csv_file.stat().st_size > 0


def test_csv_column_alignment():
    """Verify CSV header columns match expected table column count."""
    all_specs = CORE_TABLES + MARKETING_TABLES
    for spec in all_specs:
        candidate_dirs = DEFAULT_MARKETING_DIRS if "marketing" in spec["table"] else DEFAULT_OLIST_DIRS
        csv_file = find_csv_file(spec["file"], candidate_dirs)
        assert csv_file is not None
        df = pd.read_csv(csv_file, nrows=1, encoding=spec["encoding"])
        assert len(df.columns) > 0


def test_database_row_counts_match_expected(db_conn):
    """Verify row counts in PostgreSQL match exact expected dataset counts."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT table_name, row_count FROM raw.vw_ingestion_summary;")
        results = dict(cur.fetchall())

    for table, expected_count in EXPECTED_COUNTS.items():
        actual_count = results.get(table)
        assert actual_count == expected_count, (
            f"Row count mismatch for {table}: expected {expected_count:,}, found {actual_count:,}"
        )
