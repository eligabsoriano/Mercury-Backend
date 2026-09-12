"""
etl/ingest.py
=============
Mercury raw data ingestion runner.

Loads Olist Brazilian E-Commerce and Marketing Funnel CSV datasets into
PostgreSQL raw and raw_marketing schemas using PostgreSQL's COPY protocol
for high throughput.

Usage
-----
    # Ingest all datasets (core e-commerce + marketing funnel):
    python etl/ingest.py

    # Truncate tables before ingesting (clean re-load):
    python etl/ingest.py --truncate

    # Ingest core e-commerce dataset only:
    python etl/ingest.py --module core

    # Ingest marketing funnel only:
    python etl/ingest.py --module marketing

Requirements
------------
    DATABASE_URL configured in .env
    sql/schema.sql applied (via python sql/migrate.py)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Project Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

# Default candidate directories for datasets
DEFAULT_OLIST_DIRS = [
    REPO_ROOT / "dataset" / "Brazilian E-Commerce-Public-Dataset-by-Olist",
    REPO_ROOT / "dataset",
    REPO_ROOT / "Brazilian E-Commerce-Public-Dataset-by-Olist",
    REPO_ROOT / "data" / "raw" / "olist",
    REPO_ROOT / "data" / "raw",
    REPO_ROOT / "tests" / "fixtures" / "sample_data",
]

DEFAULT_MARKETING_DIRS = [
    REPO_ROOT / "dataset" / "Marketing-Funnel-by-Olist",
    REPO_ROOT / "dataset",
    REPO_ROOT / "Marketing-Funnel-by-Olist",
    REPO_ROOT / "data" / "raw" / "marketing",
    REPO_ROOT / "data" / "raw",
    REPO_ROOT / "tests" / "fixtures" / "sample_data",
]

# ---------------------------------------------------------------------------
# Table to File Specification
# Ordered strictly by foreign key dependency:
#   1. Independent dimensions
#   2. Orders
#   3. Dependent order facts (items, payments, reviews)
#   4. Marketing MQL
#   5. Marketing closed deals (depends on MQL)
# ---------------------------------------------------------------------------
CORE_TABLES: List[Dict[str, str]] = [
    {
        "table": "raw.category_translations",
        "file": "product_category_name_translation.csv",
        "encoding": "utf-8-sig",
        "expected_rows": 71,
    },
    {
        "table": "raw.geolocation",
        "file": "olist_geolocation_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 1000163,
    },
    {
        "table": "raw.products",
        "file": "olist_products_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 32951,
    },
    {
        "table": "raw.sellers",
        "file": "olist_sellers_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 3095,
    },
    {
        "table": "raw.customers",
        "file": "olist_customers_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 99441,
    },
    {
        "table": "raw.orders",
        "file": "olist_orders_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 99441,
    },
    {
        "table": "raw.order_items",
        "file": "olist_order_items_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 112650,
    },
    {
        "table": "raw.order_payments",
        "file": "olist_order_payments_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 103886,
    },
    {
        "table": "raw.order_reviews",
        "file": "olist_order_reviews_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 99224,
    },
]

MARKETING_TABLES: List[Dict[str, str]] = [
    {
        "table": "raw_marketing.mql",
        "file": "olist_marketing_qualified_leads_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 8000,
    },
    {
        "table": "raw_marketing.closed_deals",
        "file": "olist_closed_deals_dataset.csv",
        "encoding": "utf-8",
        "expected_rows": 842,
    },
]


def load_database_url() -> str:
    """Load DATABASE_URL from .env file."""
    load_dotenv(REPO_ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        print("[ERROR] DATABASE_URL is not set in .env", file=sys.stderr)
        sys.exit(1)
    return url


def mask_url(url: str) -> str:
    """Return masked database connection string for safe logging."""
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    credentials, host_part = rest.split("@", 1)
    user = credentials.split(":")[0]
    return f"{scheme}://{user}:***@{host_part}"


def find_csv_file(filename: str, candidate_dirs: List[Path]) -> Optional[Path]:
    """Search for a CSV file across candidate directory locations."""
    for directory in candidate_dirs:
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    return None


def truncate_tables(cursor: "psycopg2.cursor", tables: List[str]) -> None:
    """Truncate tables in reverse dependency order."""
    print("\n── Truncating Tables ───────────────────────────────────────")
    for table in reversed(tables):
        print(f"  → Truncating {table} ...", end=" ", flush=True)
        cursor.execute(f"TRUNCATE TABLE {table} CASCADE;")
        print("OK")


def copy_csv(cursor: "psycopg2.cursor", table_name: str, csv_path: Path, encoding: str) -> int:
    """Load a CSV file into a table using PostgreSQL COPY FROM STDIN."""
    copy_sql = f"""
        COPY {table_name}
        FROM STDIN
        WITH (
            FORMAT CSV,
            HEADER TRUE,
            NULL ''
        );
    """
    with open(csv_path, "r", encoding=encoding) as f:
        cursor.copy_expert(copy_sql, f)

    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
    return cursor.fetchone()[0]


def verify_ingestion(cursor: "psycopg2.cursor") -> None:
    """Verify row counts across tables via raw.vw_ingestion_summary."""
    print("\n── Verification (raw.vw_ingestion_summary) ─────────────────")
    cursor.execute("SELECT table_name, row_count FROM raw.vw_ingestion_summary ORDER BY table_name;")
    rows = cursor.fetchall()
    for table_name, count in rows:
        print(f"  {table_name:<32} : {count:>10,} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mercury CSV Data Ingestion Runner")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate target tables before loading CSVs",
    )
    parser.add_argument(
        "--module",
        choices=["all", "core", "marketing"],
        default="all",
        help="Dataset scope: 'core' (e-commerce), 'marketing' (funnel), or 'all' (default)",
    )
    args = parser.parse_args()

    print("Mercury — Raw Data Ingestion (PostgreSQL COPY)")
    print("=" * 60)

    db_url = load_database_url()
    print(f"  Database : {mask_url(db_url)}")
    print(f"  Module   : {args.module.upper()}")
    print(f"  Truncate : {args.truncate}")

    target_specs: List[Dict[str, str]] = []
    if args.module in ("all", "core"):
        target_specs.extend(CORE_TABLES)
    if args.module in ("all", "marketing"):
        target_specs.extend(MARKETING_TABLES)

    # Resolve all files before starting transaction
    plan: List[Tuple[Dict[str, str], Path]] = []
    print("\n── Resolving Datasets ───────────────────────────────────────")
    for spec in target_specs:
        candidate_dirs = DEFAULT_MARKETING_DIRS if "marketing" in spec["table"] else DEFAULT_OLIST_DIRS
        resolved = find_csv_file(spec["file"], candidate_dirs)
        if not resolved:
            print(f"[ERROR] Could not find required CSV file: {spec['file']}", file=sys.stderr)
            sys.exit(1)
        print(f"  Found {spec['table']:<28} -> {resolved.name} ({resolved.stat().st_size / 1024 / 1024:.1f} MB)")
        plan.append((spec, resolved))

    try:
        conn = psycopg2.connect(db_url)
    except Exception as exc:
        print(f"[ERROR] Cannot connect to database: {exc}", file=sys.stderr)
        sys.exit(1)

    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            if args.truncate:
                table_names = [spec["table"] for spec, _ in plan]
                truncate_tables(cur, table_names)

            print("\n── Ingesting Data ───────────────────────────────────────────")
            total_start = time.time()
            total_rows_loaded = 0

            for spec, csv_path in plan:
                table = spec["table"]
                t0 = time.time()
                print(f"  → Ingesting {table:<28} ...", end=" ", flush=True)

                row_count = copy_csv(cur, table, csv_path, spec["encoding"])
                conn.commit()

                elapsed = time.time() - t0
                print(f"OK ({row_count:,} rows in {elapsed:.2f}s)")
                total_rows_loaded += row_count

            total_elapsed = time.time() - total_start
            print(f"\nIngestion finished: {total_rows_loaded:,} total rows in {total_elapsed:.1f}s.")

            verify_ingestion(cur)

    except Exception as exc:
        conn.rollback()
        print(f"\n[ERROR] Ingestion failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    print("\n✅ Raw ingestion completed successfully.\n")


if __name__ == "__main__":
    main()
