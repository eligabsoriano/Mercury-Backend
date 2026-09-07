"""
ml/rfm.py
=========
RFM Segmentation Engine for Mercury.

Workflow
--------
1. Query ``mart.mart_customer_metrics`` (already aggregated by customer_unique_id).
2. Score Recency (R) and Monetary (M) into quintiles 1–5.
   - Recency is INVERTED: lower recency_days = more recent = higher R score.
3. Score Frequency (F) using behavioral tiers to handle the Olist distribution
   skew (~96.9 % of customers have exactly 1 order).
4. Compute a composite RFM score and assign named customer segments.
5. Write (upsert) the results to ``ml.rfm_segments`` in PostgreSQL.
6. Emit a plain-text segment summary to stdout.

Segment definitions (see docs/methodology.md §4):
  Champions          — R 4-5, M 4-5 (regardless of F)
  Loyal Customers    — F >= 2 (repeat buyer), R 3-5, M 3-5
  Potential Loyalists— R 4-5, M 3-4, F = 1 (high-value first-timers)
  New Customers      — R 4-5, M 1-2 (recent but low spend)
  At Risk            — R 1-2, M 4-5 (high-value gone quiet)
  Lost / Inactive    — R 1-2, M 1-2 (lapsed + low value)
  Others             — all remaining combinations

Usage
-----
  python -m ml.rfm                      # default 90-day window
  python -m ml.rfm --window 180         # override churn window (informational only)
  python -m ml.rfm --dry-run            # score only, skip DB write

Environment
-----------
Reads DATABASE_URL from .env (dotenv) or the process environment.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent

SEG_CHAMPIONS = "Champions"
SEG_LOYAL = "Loyal Customers"
SEG_POTENTIAL = "Potential Loyalists"
SEG_NEW = "New Customers"
SEG_AT_RISK = "At Risk"
SEG_LOST = "Lost / Inactive"
SEG_OTHERS = "Others"

# ---------------------------------------------------------------------------
# DDL for the output table
# ---------------------------------------------------------------------------
DDL_SCHEMA = "CREATE SCHEMA IF NOT EXISTS ml;"

DDL_TABLE = """
CREATE TABLE IF NOT EXISTS ml.rfm_segments (
    customer_unique_id      VARCHAR(50)     PRIMARY KEY,
    recency_days            INTEGER         NOT NULL,
    frequency               INTEGER         NOT NULL,
    monetary                NUMERIC(12, 2)  NOT NULL,
    r_score                 SMALLINT        NOT NULL,
    f_score                 SMALLINT        NOT NULL,
    m_score                 SMALLINT        NOT NULL,
    rfm_score               NUMERIC(4, 2)   NOT NULL,
    rfm_label               VARCHAR(100)    NOT NULL,
    segment                 VARCHAR(50)     NOT NULL,
    computed_at             TIMESTAMPTZ     NOT NULL DEFAULT now()
);
"""

# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------
QUERY_METRICS = """
SELECT
    customer_unique_id,
    recency_days,
    lifetime_orders   AS frequency,
    lifetime_spend    AS monetary
FROM mart.mart_customer_metrics
WHERE recency_days  IS NOT NULL
  AND lifetime_spend IS NOT NULL
  AND lifetime_orders IS NOT NULL;
"""

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _quintile_score(series: pd.Series, ascending: bool = True) -> pd.Series:
    """
    Assign quintile ranks 1-5 using pd.qcut with duplicates='drop'.
    ascending=False inverts so that lower raw values get higher scores (used for Recency).
    """
    labels = [1, 2, 3, 4, 5]
    try:
        if ascending:
            return pd.qcut(series, q=5, labels=labels, duplicates="drop").astype(int)
        else:
            return pd.qcut(-series, q=5, labels=labels, duplicates="drop").astype(int)
    except ValueError:
        pct = series.rank(pct=True)
        if not ascending:
            pct = 1 - pct
        return pd.cut(pct, bins=5, labels=labels, include_lowest=True).astype(int)


def score_frequency(frequency: pd.Series) -> pd.Series:
    """
    Behavioral frequency tiers to handle the Olist skew
    (~96.9% of customers have exactly 1 order).

    Tiers:
      5 — 5+ orders
      4 — 3-4 orders
      3 — exactly 2 orders  (crossed the repeat-buyer threshold)
      1 — exactly 1 order   (single-purchase customer)
    """
    scores = pd.Series(1, index=frequency.index, dtype=int)
    scores[frequency == 1] = 1
    scores[frequency == 2] = 3
    scores[(frequency >= 3) & (frequency <= 4)] = 4
    scores[frequency >= 5] = 5
    return scores


def assign_segment(row: pd.Series) -> str:
    """
    Map (r_score, f_score, m_score) to a named segment.
    Segments are checked in priority order.
    """
    r, f, m = row["r_score"], row["f_score"], row["m_score"]

    if r >= 4 and m >= 4:
        return SEG_CHAMPIONS

    if f >= 3 and r >= 3 and m >= 3:
        return SEG_LOYAL

    if r >= 4 and m >= 3 and f <= 2:
        return SEG_POTENTIAL

    if r >= 4 and m <= 2:
        return SEG_NEW

    if r <= 2 and m >= 4:
        return SEG_AT_RISK

    if r <= 2 and m <= 2:
        return SEG_LOST

    return SEG_OTHERS


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_connection(url: str):
    conn = psycopg2.connect(url)
    conn.autocommit = False
    return conn


def _ensure_table(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(DDL_SCHEMA)
        cur.execute(DDL_TABLE)
    conn.commit()
    log.info("ml.rfm_segments table ready.")


def _upsert_segments(conn, df: pd.DataFrame) -> int:
    """Upsert RFM segment rows using INSERT ... ON CONFLICT DO UPDATE."""
    upsert_sql = """
    INSERT INTO ml.rfm_segments (
        customer_unique_id, recency_days, frequency, monetary,
        r_score, f_score, m_score, rfm_score, rfm_label, segment, computed_at
    ) VALUES %s
    ON CONFLICT (customer_unique_id) DO UPDATE SET
        recency_days  = EXCLUDED.recency_days,
        frequency     = EXCLUDED.frequency,
        monetary      = EXCLUDED.monetary,
        r_score       = EXCLUDED.r_score,
        f_score       = EXCLUDED.f_score,
        m_score       = EXCLUDED.m_score,
        rfm_score     = EXCLUDED.rfm_score,
        rfm_label     = EXCLUDED.rfm_label,
        segment       = EXCLUDED.segment,
        computed_at   = now();
    """
    now = pd.Timestamp.utcnow()
    records = [
        (
            row.customer_unique_id,
            int(row.recency_days),
            int(row.frequency),
            float(row.monetary),
            int(row.r_score),
            int(row.f_score),
            int(row.m_score),
            float(row.rfm_score),
            row.rfm_label,
            row.segment,
            now,
        )
        for row in df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, upsert_sql, records, page_size=2000)
    conn.commit()
    return len(records)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

def run_rfm(database_url: str, dry_run: bool = False) -> pd.DataFrame:
    """
    Full RFM pipeline.

    Parameters
    ----------
    database_url : PostgreSQL DSN string.
    dry_run      : If True, compute scores but do not write to the database.

    Returns
    -------
    pd.DataFrame with RFM scores and segments for all customers.
    """
    log.info("Connecting to database ...")
    # Use SQLAlchemy engine for pd.read_sql (avoids DBAPI2 warning)
    engine = create_engine(database_url)
    conn = _get_connection(database_url)
    try:
        log.info("Loading mart.mart_customer_metrics ...")
        with engine.connect() as sa_conn:
            df = pd.read_sql(text(QUERY_METRICS), sa_conn)
        log.info("  Loaded %s customers.", f"{len(df):,}")

        # Score R, F, M
        log.info("Scoring R, F, M ...")
        df["r_score"] = _quintile_score(df["recency_days"], ascending=False)
        df["f_score"] = score_frequency(df["frequency"])
        df["m_score"] = _quintile_score(df["monetary"], ascending=True)

        # Composite score: simple unweighted mean (range 1.0 - 5.0)
        df["rfm_score"] = df[["r_score", "f_score", "m_score"]].mean(axis=1).round(2)

        # Human-readable label e.g. "543"
        df["rfm_label"] = (
            df["r_score"].astype(str)
            + df["f_score"].astype(str)
            + df["m_score"].astype(str)
        )

        # Segment assignment
        log.info("Assigning customer segments ...")
        df["segment"] = df.apply(assign_segment, axis=1)

        # Write to DB
        if not dry_run:
            _ensure_table(conn)
            written = _upsert_segments(conn, df)
            log.info("  Upserted %s rows into ml.rfm_segments.", f"{written:,}")
        else:
            log.info("  [DRY RUN] Skipping database write.")

    finally:
        conn.close()

    return df


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_summary(df: pd.DataFrame) -> None:
    """Print a concise segment distribution summary to stdout."""
    total = len(df)
    summary = (
        df.groupby("segment")
        .agg(
            customers=("customer_unique_id", "count"),
            avg_recency_days=("recency_days", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_monetary=("monetary", "mean"),
            avg_rfm_score=("rfm_score", "mean"),
        )
        .sort_values("customers", ascending=False)
    )
    summary["pct_of_base"] = (summary["customers"] / total * 100).round(1)

    pd.set_option("display.float_format", "{:,.1f}".format)
    pd.set_option("display.max_columns", 10)
    pd.set_option("display.width", 120)

    print("\n" + "=" * 70)
    print("  Mercury RFM Segment Summary")
    print("=" * 70)
    print(summary.to_string())
    print("-" * 70)
    print(f"  Total customers scored: {total:,}")
    print("=" * 70 + "\n")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mercury RFM Segmentation Engine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--window",
        type=int,
        default=90,
        help="Churn observation window in days (informational; used by Phase 6).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute scores but do not write to the database.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env",
        help="Path to the .env file containing DATABASE_URL.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    load_dotenv(args.env_file)
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        log.error("DATABASE_URL is not set. Add it to %s or export it.", args.env_file)
        sys.exit(1)

    log.info(
        "Starting RFM segmentation (window=%d days, dry_run=%s).",
        args.window,
        args.dry_run,
    )
    df = run_rfm(database_url=database_url, dry_run=args.dry_run)
    print_summary(df)
    log.info("Phase 5 complete.")


if __name__ == "__main__":
    main()
