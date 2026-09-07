"""
tests/test_churn.py
===================
Validates the Churn Prediction & Revenue-at-Risk engine (ml/churn.py).

Tests are organized into two groups:
  - Unit tests: Pure Python, fast, no database connection required.
    Validates feature engineering, risk tiers, priority decision matrix,
    revenue-at-risk formula, model training on synthetic data, and artifact
    serialization.
  - Integration tests: Require live DATABASE_URL and database access.
    Validates end-to-end data loading, candidate model evaluation on real
    customer intelligence metrics, database upsert to ml.churn_predictions,
    and artifact persistence.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd
import psycopg2
import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

# Import module under test
from ml.churn import (
    CATEGORICAL_FEATURES,
    DEFAULT_ARTIFACT_PATH,
    NUMERIC_FEATURES,
    PRIORITY_LOYALTY,
    PRIORITY_MEDIUM,
    PRIORITY_REENGAGEMENT,
    PRIORITY_STANDARD,
    PRIORITY_VIP,
    RISK_TIER_HIGH,
    RISK_TIER_LOW,
    RISK_TIER_MEDIUM,
    assign_retention_priority,
    assign_risk_tier,
    compute_revenue_at_risk,
    create_preprocessor,
    engineer_features,
    load_model_artifact,
    run_churn_pipeline,
    save_model_artifact,
    train_candidate_models,
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
def synthetic_customer_df() -> pd.DataFrame:
    """Generate a clean synthetic DataFrame with all required mart + RFM columns."""
    np.random.seed(42)
    n = 200
    return pd.DataFrame({
        "customer_unique_id": [f"cust_{i:04d}" for i in range(n)],
        "first_purchased_at": pd.date_range("2017-01-01", periods=n, freq="D", tz="UTC"),
        "latest_purchased_at": pd.date_range("2017-06-01", periods=n, freq="D", tz="UTC"),
        "recency_days": np.random.randint(10, 300, size=n),
        "customer_lifespan_days": np.random.randint(0, 100, size=n),
        "lifetime_orders": np.random.choice([1, 2, 3], size=n, p=[0.90, 0.08, 0.02]),
        "is_repeat_buyer": np.random.choice([False, True], size=n, p=[0.90, 0.10]),
        "lifetime_spend": np.random.uniform(20.0, 1500.0, size=n).round(2),
        "lifetime_product_spend": np.random.uniform(15.0, 1200.0, size=n).round(2),
        "lifetime_freight_spend": np.random.uniform(5.0, 100.0, size=n).round(2),
        "avg_order_value": np.random.uniform(20.0, 800.0, size=n).round(2),
        "lifetime_items": np.random.randint(1, 5, size=n),
        "avg_items_per_order": np.random.uniform(1.0, 3.0, size=n).round(2),
        "total_unique_products_purchased": np.random.randint(1, 4, size=n),
        "total_unique_sellers_contacted": np.random.randint(1, 3, size=n),
        "avg_delivery_delay_days": np.random.uniform(-15.0, 10.0, size=n).round(2),
        "max_delivery_delay_days": np.random.uniform(-10.0, 15.0, size=n).round(2),
        "late_orders_count": np.random.choice([0, 1], size=n, p=[0.92, 0.08]),
        "on_time_orders_count": np.random.choice([1, 2], size=n, p=[0.92, 0.08]),
        "late_order_ratio": np.random.uniform(0.0, 0.5, size=n).round(2),
        "has_late_delivery": np.random.choice([False, True], size=n, p=[0.92, 0.08]),
        "total_reviews_submitted": np.random.randint(0, 3, size=n),
        "avg_review_score": np.random.choice([1.0, 2.0, 3.0, 4.0, 5.0, np.nan], size=n),
        "negative_reviews_count": np.random.choice([0, 1], size=n, p=[0.85, 0.15]),
        "positive_reviews_count": np.random.choice([0, 1, 2], size=n, p=[0.2, 0.7, 0.1]),
        "has_negative_review": np.random.choice([False, True], size=n, p=[0.85, 0.15]),
        "negative_review_ratio": np.random.uniform(0.0, 0.3, size=n).round(2),
        "f_score": np.random.choice([1, 3, 4, 5], size=n, p=[0.90, 0.07, 0.02, 0.01]),
        "m_score": np.random.choice([1, 2, 3, 4, 5], size=n),
        "segment": np.random.choice(
            ["Champions", "Loyal Customers", "Potential Loyalists", "New Customers", "At Risk", "Lost / Inactive", "Others"],
            size=n,
        ),
    })


# ---------------------------------------------------------------------------
# Unit Tests — Pure Python
# ---------------------------------------------------------------------------

class TestRiskTierAssignment:
    def test_high_risk_tier(self):
        assert assign_risk_tier(0.70) == RISK_TIER_HIGH
        assert assign_risk_tier(0.85) == RISK_TIER_HIGH
        assert assign_risk_tier(1.00) == RISK_TIER_HIGH

    def test_medium_risk_tier(self):
        assert assign_risk_tier(0.30) == RISK_TIER_MEDIUM
        assert assign_risk_tier(0.50) == RISK_TIER_MEDIUM
        assert assign_risk_tier(0.6999) == RISK_TIER_MEDIUM

    def test_low_risk_tier(self):
        assert assign_risk_tier(0.00) == RISK_TIER_LOW
        assert assign_risk_tier(0.15) == RISK_TIER_LOW
        assert assign_risk_tier(0.2999) == RISK_TIER_LOW


class TestRetentionPriorityMatrix:
    def test_priority_1_vip_retention(self):
        # High Monetary (m_score >= 4) & High Churn (P >= 0.70)
        assert assign_retention_priority(0.75, 4) == PRIORITY_VIP
        assert assign_retention_priority(0.90, 5) == PRIORITY_VIP

    def test_priority_2_loyalty_and_nurture(self):
        # High Monetary (m_score >= 4) & Low Churn (P < 0.30)
        assert assign_retention_priority(0.10, 4) == PRIORITY_LOYALTY
        assert assign_retention_priority(0.25, 5) == PRIORITY_LOYALTY

    def test_priority_3_automated_reengagement(self):
        # Low Monetary (m_score <= 2) & High Churn (P >= 0.70)
        assert assign_retention_priority(0.75, 1) == PRIORITY_REENGAGEMENT
        assert assign_retention_priority(0.80, 2) == PRIORITY_REENGAGEMENT

    def test_priority_4_standard_operations(self):
        # Low Monetary (m_score <= 2) & Low Churn (P < 0.30)
        assert assign_retention_priority(0.15, 1) == PRIORITY_STANDARD
        assert assign_retention_priority(0.20, 2) == PRIORITY_STANDARD

    def test_medium_priority_fallthrough(self):
        # Medium risk or medium monetary combinations
        assert assign_retention_priority(0.50, 3) == PRIORITY_MEDIUM
        assert assign_retention_priority(0.50, 5) == PRIORITY_MEDIUM
        assert assign_retention_priority(0.15, 3) == PRIORITY_MEDIUM


class TestRevenueAtRiskCalculation:
    def test_positive_values(self):
        assert compute_revenue_at_risk(0.80, 100.0) == 80.0
        assert compute_revenue_at_risk(0.50, 150.0) == 75.0
        assert compute_revenue_at_risk(0.3333, 150.0) == pytest.approx(50.0, abs=0.02)
        assert compute_revenue_at_risk(0.50, 49.99) == 25.0

    def test_zero_churn_probability(self):
        assert compute_revenue_at_risk(0.0, 500.0) == 0.0

    def test_zero_monetary_value(self):
        assert compute_revenue_at_risk(0.95, 0.0) == 0.0


class TestFeatureEngineering:
    def test_churn_label_creation(self, synthetic_customer_df):
        engineered = engineer_features(synthetic_customer_df, window_days=90)
        assert "is_churned" in engineered.columns
        expected_churn = (synthetic_customer_df["recency_days"] > 90).astype(int)
        pd.testing.assert_series_equal(engineered["is_churned"], expected_churn, check_names=False)

    def test_window_days_parameter_impacts_label(self, synthetic_customer_df):
        eng_90 = engineer_features(synthetic_customer_df, window_days=90)
        eng_180 = engineer_features(synthetic_customer_df, window_days=180)
        # Higher window must have <= churn count
        assert eng_180["is_churned"].sum() <= eng_90["is_churned"].sum()

    def test_boolean_flags_converted_to_int(self, synthetic_customer_df):
        engineered = engineer_features(synthetic_customer_df, window_days=90)
        for col in ["is_repeat_buyer", "has_late_delivery", "has_negative_review"]:
            assert set(engineered[col].unique()).issubset({0, 1})

    def test_freight_ratio_computation(self, synthetic_customer_df):
        engineered = engineer_features(synthetic_customer_df, window_days=90)
        assert "freight_ratio" in engineered.columns
        assert (engineered["freight_ratio"] >= 0.0).all()


class TestPreprocessorAndCandidateModels:
    def test_preprocessor_transforms_features_without_error(self, synthetic_customer_df):
        engineered = engineer_features(synthetic_customer_df, window_days=90)
        preprocessor = create_preprocessor(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        transformed = preprocessor.fit_transform(engineered)
        assert transformed.shape[0] == len(engineered)
        assert not np.isnan(transformed).any()

    def test_train_candidate_models_selects_winner(self, synthetic_customer_df):
        engineered = engineer_features(synthetic_customer_df, window_days=90)
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        X = engineered[features]
        y = engineered["is_churned"].values

        # Ensure both classes present in small test
        if len(np.unique(y)) < 2:
            y[0] = 0
            y[1] = 1

        X_train, X_test = X.iloc[:150], X.iloc[150:]
        y_train, y_test = y[:150], y[150:]

        preprocessor = create_preprocessor(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        best_name, best_pipeline, results = train_candidate_models(
            X_train, y_train, X_test, y_test, preprocessor
        )

        assert best_name in ["Logistic Regression", "Random Forest", "HistGradientBoosting"]
        assert len(results) == 3
        for r in results:
            assert "auc" in r and "f1" in r and "precision_at_k" in r

    def test_artifact_serialization_and_inference(self, synthetic_customer_df, tmp_path):
        engineered = engineer_features(synthetic_customer_df, window_days=90)
        features = NUMERIC_FEATURES + CATEGORICAL_FEATURES
        X = engineered[features]
        y = engineered["is_churned"].values
        if len(np.unique(y)) < 2:
            y[0] = 0
            y[1] = 1

        preprocessor = create_preprocessor(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
        best_name, best_pipeline, results = train_candidate_models(
            X, y, X, y, preprocessor
        )

        artifact_file = tmp_path / "test_churn_model.joblib"
        artifact_data = {
            "model_name": best_name,
            "pipeline": best_pipeline,
            "features": {"numeric": NUMERIC_FEATURES, "categorical": CATEGORICAL_FEATURES},
            "eval_results": results,
            "window_days": 90,
        }
        save_model_artifact(artifact_data, output_path=artifact_file)
        assert artifact_file.exists()

        # Load and run inference
        loaded = load_model_artifact(artifact_file)
        assert loaded["model_name"] == best_name
        loaded_pipe = loaded["pipeline"]
        probs = loaded_pipe.predict_proba(X.iloc[:5])[:, 1]
        assert len(probs) == 5
        assert (probs >= 0.0).all() and (probs <= 1.0).all()


# ---------------------------------------------------------------------------
# Integration Tests — Requires Live Neon PostgreSQL
# ---------------------------------------------------------------------------

class TestChurnPipelineIntegration:
    """Integration test suite executing against PostgreSQL mart tables."""

    @pytest.fixture(scope="class")
    def pipeline_run(self, db_conn):
        """Execute full churn pipeline with database write enabled."""
        load_dotenv(REPO_ROOT / ".env")
        url = os.getenv("DATABASE_URL")
        df_scored, eval_results, summary = run_churn_pipeline(
            database_url=url,
            window_days=90,
            dry_run=False,
            artifact_path=DEFAULT_ARTIFACT_PATH,
        )
        return df_scored, eval_results, summary

    def test_pipeline_scores_all_customers(self, pipeline_run, db_conn):
        df_scored, _, _ = pipeline_run
        with db_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mart.mart_customer_metrics;")
            expected_count = cur.fetchone()[0]
        assert len(df_scored) == expected_count == 93358

    def test_candidate_models_evaluated(self, pipeline_run):
        _, eval_results, summary = pipeline_run
        names = {r["name"] for r in eval_results}
        expected_candidates = {"Logistic Regression", "Random Forest", "HistGradientBoosting"}
        assert names == expected_candidates
        for r in eval_results:
            assert 0.50 <= r["auc"] <= 1.00, f"Unrealistic AUC {r['auc']} for {r['name']}"
            assert 0.00 <= r["precision_at_k"] <= 1.00

    def test_churn_probabilities_within_valid_bounds(self, pipeline_run):
        df_scored, _, _ = pipeline_run
        probs = df_scored["churn_probability"]
        assert probs.between(0.0, 1.0).all()
        assert not probs.isna().any()

    def test_risk_tiers_distribution_valid(self, pipeline_run):
        df_scored, _, _ = pipeline_run
        valid_tiers = {RISK_TIER_HIGH, RISK_TIER_MEDIUM, RISK_TIER_LOW}
        found_tiers = set(df_scored["risk_tier"].unique())
        assert found_tiers.issubset(valid_tiers)
        assert not df_scored["risk_tier"].isna().any()

    def test_retention_priorities_valid(self, pipeline_run):
        df_scored, _, _ = pipeline_run
        valid_priorities = {
            PRIORITY_VIP,
            PRIORITY_LOYALTY,
            PRIORITY_REENGAGEMENT,
            PRIORITY_STANDARD,
            PRIORITY_MEDIUM,
        }
        found_priorities = set(df_scored["retention_priority"].unique())
        assert found_priorities.issubset(valid_priorities)

    def test_revenue_at_risk_mathematical_consistency(self, pipeline_run):
        df_scored, _, summary = pipeline_run
        expected_rar = (df_scored["churn_probability"] * df_scored["monetary_value"]).round(2)
        diff = (df_scored["revenue_at_risk"] - expected_rar).abs()
        assert (diff <= 0.02).all(), "Revenue at risk deviates from P(Churn) * monetary_value"
        assert summary["total_revenue_at_risk"] > 0.0

    def test_database_table_exists_and_row_count_matches(self, pipeline_run, db_conn):
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'ml' AND table_name = 'churn_predictions';
            """)
            assert cur.fetchone()[0] == 1, "ml.churn_predictions table not found."

            cur.execute("SELECT COUNT(*) FROM ml.churn_predictions;")
            db_count = cur.fetchone()[0]
            assert db_count == 93358, f"Expected 93,358 rows in ml.churn_predictions, got {db_count}"

    def test_database_has_no_nulls_in_critical_columns(self, pipeline_run, db_conn):
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE customer_unique_id IS NULL) AS null_cust,
                    COUNT(*) FILTER (WHERE is_churned IS NULL) AS null_churn,
                    COUNT(*) FILTER (WHERE churn_probability IS NULL) AS null_prob,
                    COUNT(*) FILTER (WHERE risk_tier IS NULL) AS null_tier,
                    COUNT(*) FILTER (WHERE revenue_at_risk IS NULL) AS null_rar,
                    COUNT(*) FILTER (WHERE retention_priority IS NULL) AS null_prio
                FROM ml.churn_predictions;
            """)
            null_counts = cur.fetchone()
        assert all(c == 0 for c in null_counts), f"Found nulls in churn predictions: {null_counts}"

    def test_database_indexes_created(self, pipeline_run, db_conn):
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'ml' AND tablename = 'churn_predictions';
            """)
            indexes = {row[0] for row in cur.fetchall()}
        assert "idx_churn_predictions_risk_tier" in indexes
        assert "idx_churn_predictions_retention_priority" in indexes
        assert "idx_churn_predictions_revenue_at_risk" in indexes

    def test_model_artifact_saved_and_loadable(self, pipeline_run):
        assert DEFAULT_ARTIFACT_PATH.exists(), f"Model artifact missing at {DEFAULT_ARTIFACT_PATH}"
        artifact = load_model_artifact(DEFAULT_ARTIFACT_PATH)
        assert "model_name" in artifact
        assert "pipeline" in artifact
        assert "eval_results" in artifact
        assert "features" in artifact
