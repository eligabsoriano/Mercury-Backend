"""
sql/migrate.py
==============
Mercury database migration runner.

Drops the old Online Retail II schema (if present), then applies the new
Olist-based raw schema (sql/schema.sql) and helper views (sql/views.sql).

Safe to re-run:
  - DROP statements use IF EXISTS.
  - CREATE statements use IF NOT EXISTS / CREATE OR REPLACE.

Usage
-----
    # From the repository root:
    python sql/migrate.py

    # Full reset (re-drops schemas even if current):
    python sql/migrate.py --reset

Requirements
------------
    DATABASE_URL must be set in .env (copy from .env.example and fill in values).
    pip install -r requirements.txt

Neon note
---------
    Neon connection strings include ?sslmode=require.  psycopg2-binary handles
    this automatically when sslmode is in the DATABASE_URL.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR   = Path(__file__).resolve().parent

SCHEMA_FILE = SQL_DIR / "schema.sql"
VIEWS_FILE  = SQL_DIR / "views.sql"

# ---------------------------------------------------------------------------
# Old Online Retail II tables to drop on reset
# These no longer exist in the Olist schema.
# ---------------------------------------------------------------------------
OLD_TABLES = [
    "customer_metrics",
    "order_items",
    "orders",
    "customers",
    "products",
    "countries",
]

OLD_VIEWS = [
    "vw_at_risk_customers",
    "vw_customer_revenue",
    "vw_revenue_at_risk_summary",
    "vw_rfm_base",
    "vw_segment_summary",
]

# ---------------------------------------------------------------------------
# Expected post-migration objects
# ---------------------------------------------------------------------------
EXPECTED_TABLES = {
    "raw.customers",
    "raw.orders",
    "raw.order_items",
    "raw.order_payments",
    "raw.order_reviews",
    "raw.products",
    "raw.sellers",
    "raw.geolocation",
    "raw.category_translations",
    "raw_marketing.mql",
    "raw_marketing.closed_deals",
}

EXPECTED_VIEWS = {
    "raw.vw_delivered_orders",
    "raw.vw_order_revenue",
    "raw.vw_ingestion_summary",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_database_url() -> str:
    """Load DATABASE_URL from .env (repository root). Abort if missing."""
    env_path = REPO_ROOT / ".env"
    load_dotenv(env_path)

    url = os.getenv("DATABASE_URL")
    if not url:
        print(
            "[ERROR] DATABASE_URL is not set.\n"
            "        Copy .env.example to .env and fill in your Neon connection string.",
            file=sys.stderr,
        )
        sys.exit(1)

    if "user:password@host" in url:
        print(
            "[ERROR] DATABASE_URL still contains the placeholder from .env.example.\n"
            "        Update .env with your real Neon connection string.",
            file=sys.stderr,
        )
        sys.exit(1)

    return url


def _mask_url(url: str) -> str:
    """Return the URL with the password replaced by ***."""
    if "://" not in url or "@" not in url:
        return url
    scheme, rest = url.split("://", 1)
    credentials, host_part = rest.split("@", 1)
    user = credentials.split(":")[0]
    return f"{scheme}://{user}:***@{host_part}"


def _read_sql(path: Path) -> str:
    if not path.exists():
        print(f"[ERROR] SQL file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def _execute_script(cursor: "psycopg2.cursor", sql: str, label: str) -> None:
    print(f"  → Applying {label} ...", end=" ", flush=True)
    try:
        cursor.execute(sql)
        print("OK")
    except psycopg2.Error as exc:
        print(f"FAILED\n[ERROR] {exc}", file=sys.stderr)
        raise


def _drop_old_schema(cursor: "psycopg2.cursor") -> None:
    """Drop Online Retail II legacy tables and views from the public schema."""
    print("  → Dropping legacy Online Retail II objects (public schema) ...", end=" ", flush=True)
    for view in OLD_VIEWS:
        cursor.execute(f'DROP VIEW IF EXISTS public."{view}" CASCADE;')
    for table in OLD_TABLES:
        cursor.execute(f'DROP TABLE IF EXISTS public."{table}" CASCADE;')
    print("OK")


def _drop_raw_schemas(cursor: "psycopg2.cursor") -> None:
    """Drop raw and raw_marketing schemas entirely (used by --reset flag)."""
    print("  → Dropping raw schemas for full reset ...", end=" ", flush=True)
    cursor.execute("DROP SCHEMA IF EXISTS raw CASCADE;")
    cursor.execute("DROP SCHEMA IF EXISTS raw_marketing CASCADE;")
    print("OK")


def _verify(cursor: "psycopg2.cursor") -> None:
    """Print a summary of schema.table pairs that now exist."""
    cursor.execute(
        """
        SELECT table_schema || '.' || table_name AS qualified
        FROM information_schema.tables
        WHERE table_schema IN ('raw', 'raw_marketing', 'staging', 'mart')
          AND table_type = 'BASE TABLE'
        ORDER BY qualified;
        """
    )
    tables = [row[0] for row in cursor.fetchall()]

    cursor.execute(
        """
        SELECT table_schema || '.' || table_name AS qualified
        FROM information_schema.views
        WHERE table_schema IN ('raw', 'raw_marketing', 'staging', 'mart')
        ORDER BY qualified;
        """
    )
    views = [row[0] for row in cursor.fetchall()]

    print("\n── Verification ─────────────────────────────────────────────")
    print(f"  Tables ({len(tables)}): {', '.join(tables) if tables else 'none'}")
    print(f"  Views  ({len(views)}):  {', '.join(views)  if views  else 'none'}")

    missing_tables = EXPECTED_TABLES - set(tables)
    missing_views  = EXPECTED_VIEWS  - set(views)

    if missing_tables:
        print(f"\n[WARNING] Missing tables: {missing_tables}", file=sys.stderr)
    if missing_views:
        print(f"[WARNING] Missing views:  {missing_views}", file=sys.stderr)

    if not missing_tables and not missing_views:
        print("\n  ✅ All expected tables and views are present.")
    else:
        print("\n  ❌ Verification failed — check warnings above.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Mercury database migration runner")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop raw and raw_marketing schemas before applying (full reset).",
    )
    args = parser.parse_args()

    print("Mercury — Database Migration Runner (Olist schema)")
    print("=" * 52)

    database_url = _load_database_url()
    print(f"  Database : {_mask_url(database_url)}")
    if args.reset:
        print("  Mode     : FULL RESET (--reset flag set — raw schemas will be dropped)")

    schema_sql = _read_sql(SCHEMA_FILE)
    views_sql  = _read_sql(VIEWS_FILE)

    print("\n── Connecting ───────────────────────────────────────────────")
    try:
        conn = psycopg2.connect(database_url)
    except psycopg2.OperationalError as exc:
        print(f"[ERROR] Cannot connect to database:\n  {exc}", file=sys.stderr)
        sys.exit(1)

    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            print("\n── Cleanup ──────────────────────────────────────────────────")
            _drop_old_schema(cur)           # always remove legacy OLR II tables
            if args.reset:
                _drop_raw_schemas(cur)      # full schema drop on --reset

            print("\n── Applying migrations ───────────────────────────────────────")
            _execute_script(cur, schema_sql, "schema.sql  (raw tables + indexes)")
            _execute_script(cur, views_sql,  "views.sql   (raw helper views)    ")
            conn.commit()

            print("\n── Schema committed ─────────────────────────────────────────")
            _verify(cur)

    except Exception:
        conn.rollback()
        print("\n[ERROR] Migration rolled back due to error above.", file=sys.stderr)
        sys.exit(1)

    finally:
        conn.close()

    print("\nDone. Raw schema is ready for CSV ingestion.\n")


if __name__ == "__main__":
    main()
