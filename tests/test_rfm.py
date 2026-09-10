"""
tests/test_rfm.py
=================
Validates the RFM segmentation engine (ml/rfm.py).

Tests are split into two groups:
  - Unit tests: pure Python, no DB required. Cover scoring and segment logic.
  - Integration tests: require DATABASE_URL and a live ml.rfm_segments table.
    They are skipped automatically when DATABASE_URL is not set.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import psycopg2
import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

# Import the module under test
from ml.rfm import (
    SEG_AT_RISK,
    SEG_CHAMPIONS,
    SEG_LOST,
    SEG_LOYAL,
    SEG_NEW,
    SEG_OTHERS,
    SEG_POTENTIAL,
    _quintile_score,
    assign_segment,
    run_rfm,
    score_frequency,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_conn():
    load_dotenv(REPO_ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not configured — skipping integration tests.")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def rfm_df(db_conn):
    """Run the full RFM pipeline in dry-run mode and return the scored DataFrame."""
    load_dotenv(REPO_ROOT / ".env")
    url = os.getenv("DATABASE_URL")
    return run_rfm(database_url=url, dry_run=True)


# ---------------------------------------------------------------------------
# Unit tests — scoring helpers
# ---------------------------------------------------------------------------


class TestQuintileScore:
    def test_ascending_returns_5_unique_labels(self):
        s = pd.Series(range(100))
        result = _quintile_score(s, ascending=True)
        assert set(result.unique()) == {1, 2, 3, 4, 5}

    def test_ascending_high_value_gets_high_score(self):
        s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        result = _quintile_score(s, ascending=True)
        assert result.iloc[-1] >= result.iloc[0]

    def test_descending_low_value_gets_high_score(self):
        # For Recency: low recency_days (very recent) should score highest
        s = pd.Series([1, 50, 100, 200, 365])
        result = _quintile_score(s, ascending=False)
        assert result.iloc[0] > result.iloc[-1]


class TestScoreFrequency:
    def test_single_order_scores_1(self):
        s = pd.Series([1, 1, 1])
        assert list(score_frequency(s)) == [1, 1, 1]

    def test_two_orders_scores_3(self):
        s = pd.Series([2])
        assert score_frequency(s).iloc[0] == 3

    def test_three_four_orders_scores_4(self):
        for n in [3, 4]:
            s = pd.Series([n])
            assert score_frequency(s).iloc[0] == 4

    def test_five_plus_orders_scores_5(self):
        for n in [5, 10, 100]:
            s = pd.Series([n])
            assert score_frequency(s).iloc[0] == 5


class TestAssignSegment:
    def _row(self, r, f, m):
        return pd.Series({"r_score": r, "f_score": f, "m_score": m})

    def test_champions_high_r_high_m(self):
        assert assign_segment(self._row(5, 1, 5)) == SEG_CHAMPIONS
        assert assign_segment(self._row(4, 1, 4)) == SEG_CHAMPIONS

    def test_loyal_repeat_buyer_solid_scores(self):
        assert assign_segment(self._row(4, 3, 4)) == SEG_CHAMPIONS  # Champions takes priority
        assert assign_segment(self._row(3, 3, 3)) == SEG_LOYAL

    def test_potential_loyalist_recent_decent_single_order(self):
        assert assign_segment(self._row(5, 1, 3)) == SEG_POTENTIAL
        assert assign_segment(self._row(4, 1, 4)) == SEG_CHAMPIONS  # Champions takes priority

    def test_new_customer_recent_low_spend(self):
        assert assign_segment(self._row(5, 1, 1)) == SEG_NEW
        assert assign_segment(self._row(4, 1, 2)) == SEG_NEW

    def test_at_risk_lapsed_high_spender(self):
        assert assign_segment(self._row(1, 1, 5)) == SEG_AT_RISK
        assert assign_segment(self._row(2, 1, 4)) == SEG_AT_RISK

    def test_lost_inactive(self):
        assert assign_segment(self._row(1, 1, 1)) == SEG_LOST
        assert assign_segment(self._row(2, 1, 2)) == SEG_LOST

    def test_others_catches_remaining(self):
        # r=3, f=1, m=3 — doesn't meet Champions, Loyal, Potential, New, At Risk, or Lost
        assert assign_segment(self._row(3, 1, 3)) == SEG_OTHERS


# ---------------------------------------------------------------------------
# Integration tests — requires live DATABASE_URL
# ---------------------------------------------------------------------------


class TestRfmPipeline:
    def test_dataframe_has_expected_columns(self, rfm_df):
        required = {
            "customer_unique_id",
            "recency_days",
            "frequency",
            "monetary",
            "r_score",
            "f_score",
            "m_score",
            "rfm_score",
            "rfm_label",
            "segment",
        }
        assert required.issubset(set(rfm_df.columns))

    def test_row_count_matches_mart(self, rfm_df, db_conn):
        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mart.mart_customer_metrics;")
            mart_count = cur.fetchone()[0]
        assert len(rfm_df) == mart_count, f"RFM scored {len(rfm_df)} rows but mart has {mart_count}"

    def test_scores_in_valid_range(self, rfm_df):
        for col in ["r_score", "f_score", "m_score"]:
            assert rfm_df[col].between(1, 5).all(), f"{col} has values outside 1-5"

    def test_rfm_score_is_mean_of_components(self, rfm_df):
        expected = rfm_df[["r_score", "f_score", "m_score"]].mean(axis=1).round(2)
        pd.testing.assert_series_equal(rfm_df["rfm_score"], expected, check_names=False)

    def test_rfm_label_format(self, rfm_df):
        """rfm_label should be a 3-character string of digits 1-5."""
        assert rfm_df["rfm_label"].str.match(r"^[1-5]{3}$").all()

    def test_no_null_segments(self, rfm_df):
        assert rfm_df["segment"].notna().all()

    def test_known_segments_present(self, rfm_df):
        valid_segments = {
            SEG_CHAMPIONS,
            SEG_LOYAL,
            SEG_POTENTIAL,
            SEG_NEW,
            SEG_AT_RISK,
            SEG_LOST,
            SEG_OTHERS,
        }
        found = set(rfm_df["segment"].unique())
        assert found.issubset(valid_segments), f"Unknown segments: {found - valid_segments}"

    def test_no_duplicate_customers(self, rfm_df):
        assert rfm_df["customer_unique_id"].is_unique

    def test_segment_distribution_sanity(self, rfm_df):
        """
        Given the Olist skew (96.9% single-order customers), the majority
        should fall into New Customers, Others, or Lost / Inactive.
        Champions and Loyal should collectively be a small minority.
        """
        counts = rfm_df["segment"].value_counts(normalize=True)
        champions_loyal_pct = counts.get(SEG_CHAMPIONS, 0) + counts.get(SEG_LOYAL, 0)
        assert champions_loyal_pct < 0.30, (
            f"Champions + Loyal = {champions_loyal_pct:.1%}, expected < 30%"
        )


class TestRfmDbWrite:
    """Verifies that the full pipeline (with DB write) creates the expected table."""

    def test_full_run_creates_rfm_segments_table(self, db_conn):
        load_dotenv(REPO_ROOT / ".env")
        url = os.getenv("DATABASE_URL")

        # Run with write enabled
        run_rfm(database_url=url, dry_run=False)

        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'ml' AND table_name = 'rfm_segments';
                """
            )
            assert cur.fetchone()[0] == 1, "ml.rfm_segments table not found after write."

    def test_row_count_in_db_matches_mart(self, db_conn):
        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ml.rfm_segments;")
            rfm_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM mart.mart_customer_metrics;")
            mart_count = cur.fetchone()[0]
        assert rfm_count == mart_count, (
            f"ml.rfm_segments has {rfm_count} rows, mart has {mart_count}"
        )

    def test_all_segments_valid_in_db(self, db_conn):
        valid_segments = (
            SEG_CHAMPIONS,
            SEG_LOYAL,
            SEG_POTENTIAL,
            SEG_NEW,
            SEG_AT_RISK,
            SEG_LOST,
            SEG_OTHERS,
        )
        placeholders = ",".join(["%s"] * len(valid_segments))
        with db_conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM ml.rfm_segments
                WHERE segment NOT IN ({placeholders});
                """,
                valid_segments,
            )
            invalid_count = cur.fetchone()[0]
        assert invalid_count == 0, f"{invalid_count} rows have unknown segment values."
