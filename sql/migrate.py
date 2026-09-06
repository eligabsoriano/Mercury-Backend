"""
sql/migrate.py
==============
Mercury database migration runner.

Applies sql/schema.sql then sql/views.sql to the target PostgreSQL database.
Safe to re-run: schema uses IF NOT EXISTS; views use CREATE OR REPLACE.

Usage
-----
    # From the repository root:
    python sql/migrate.py

Requirements
------------
    DATABASE_URL must be set in .env (copy from .env.example and fill in values).
    pip install -r requirements.txt

Neon note
---------
    Neon connection strings use ?sslmode=require.  psycopg2-binary handles this
    automatically when the DATABASE_URL includes the sslmode query parameter.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = Path(__file__).resolve().parent

SCHEMA_FILE = SQL_DIR / "schema.sql"
VIEWS_FILE = SQL_DIR / "views.sql"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_database_url() -> str:
    """Load DATABASE_URL from .env (repository root).  Abort if missing."""
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

    # Safety guard: refuse to run against example placeholder
    if "user:password@host" in url:
        print(
            "[ERROR] DATABASE_URL still contains the placeholder value from .env.example.\n"
            "        Update .env with your real Neon connection string.",
            file=sys.stderr,
        )
        sys.exit(1)

    return url


def _read_sql(path: Path) -> str:
    """Return the contents of a SQL file."""
    if not path.exists():
        print(f"[ERROR] SQL file not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def _execute_script(cursor: "psycopg2.cursor", sql: str, label: str) -> None:
    """Execute a multi-statement SQL script and print progress."""
    print(f"  → Applying {label} ...", end=" ", flush=True)
    try:
        cursor.execute(sql)
        print("OK")
    except psycopg2.Error as exc:
        print(f"FAILED\n[ERROR] {exc}", file=sys.stderr)
        raise


def _verify(cursor: "psycopg2.cursor") -> None:
    """Print a summary of tables and views that now exist in the public schema."""
    # Tables
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type   = 'BASE TABLE'
        ORDER BY table_name;
        """
    )
    tables = [row[0] for row in cursor.fetchall()]

    # Views
    cursor.execute(
        """
        SELECT table_name
        FROM information_schema.views
        WHERE table_schema = 'public'
        ORDER BY table_name;
        """
    )
    views = [row[0] for row in cursor.fetchall()]

    print("\n── Verification ─────────────────────────────────────────────")
    print(f"  Tables  ({len(tables)}): {', '.join(tables) if tables else 'none'}")
    print(f"  Views   ({len(views)}):  {', '.join(views)  if views  else 'none'}")

    expected_tables = {
        "countries", "customers", "customer_metrics",
        "order_items", "orders", "products",
    }
    expected_views = {
        "vw_at_risk_customers",
        "vw_customer_revenue",
        "vw_revenue_at_risk_summary",
        "vw_rfm_base",
        "vw_segment_summary",
    }

    missing_tables = expected_tables - set(tables)
    missing_views = expected_views - set(views)

    if missing_tables:
        print(f"\n[WARNING] Missing tables: {missing_tables}", file=sys.stderr)
    if missing_views:
        print(f"[WARNING] Missing views:  {missing_views}", file=sys.stderr)

    if not missing_tables and not missing_views:
        print("\n  ✅ All expected tables and views are present.")
    else:
        print("\n  ❌ Schema verification failed — check warnings above.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Mercury — Database Migration Runner")
    print("=" * 50)

    database_url = _load_database_url()

    # Mask password for display
    safe_url = database_url
    if "@" in database_url:
        scheme, rest = database_url.split("://", 1)
        credentials, host_part = rest.split("@", 1)
        user = credentials.split(":")[0]
        safe_url = f"{scheme}://{user}:***@{host_part}"
    print(f"  Database : {safe_url}")

    schema_sql = _read_sql(SCHEMA_FILE)
    views_sql = _read_sql(VIEWS_FILE)

    print("\n── Connecting ───────────────────────────────────────────────")
    try:
        conn = psycopg2.connect(database_url)
    except psycopg2.OperationalError as exc:
        print(f"[ERROR] Cannot connect to database:\n  {exc}", file=sys.stderr)
        sys.exit(1)

    conn.autocommit = False

    try:
        with conn.cursor() as cur:
            print("\n── Applying migrations ───────────────────────────────────────")
            _execute_script(cur, schema_sql, "schema.sql  (tables + indexes)")
            _execute_script(cur, views_sql,  "views.sql   (analytical views) ")
            conn.commit()
            print("\n── Schema committed ─────────────────────────────────────────")
            _verify(cur)

    except Exception:
        conn.rollback()
        print("\n[ERROR] Migration rolled back due to error above.", file=sys.stderr)
        sys.exit(1)

    finally:
        conn.close()

    print("\nDone. Database is ready for ETL and ML pipelines.\n")


if __name__ == "__main__":
    main()
