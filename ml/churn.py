"""
ml/churn.py
===========
Churn Prediction & Revenue-at-Risk Engine for Mercury.

Workflow
--------
1. Load customer metrics from ``mart.mart_customer_metrics`` and join with
   ``ml.rfm_segments`` on ``customer_unique_id``.
2. Define time-bounded churn label:
     is_churned = (recency_days > window_days)
   where window_days defaults to 90 days (configurable, e.g. 90 or 180 days).
3. Engineer customer intelligence features across RFM, fulfillment friction,
   review sentiment, basket composition, and customer lifespan.
   Note: Recency features (recency_days, r_score, rfm_score, rfm_label) are
   strictly excluded from the feature matrix to eliminate target leakage.
4. Perform train/test split (stratified by default, with cohort validation)
   to evaluate generalization.
5. Train candidate classifiers:
     - Logistic Regression (Baseline)
     - Random Forest Classifier
     - HistGradientBoostingClassifier (LightGBM equivalent)
6. Evaluate candidate models on test cohort:
     - ROC-AUC
     - Average Precision (PR-AUC)
     - F1-Score, Precision, Recall
     - Precision @ Top 10% (P@10%)
   Select the winning model (highest ROC-AUC).
7. Save best model artifact to ``ml/artifacts/churn_model.joblib``.
8. Predict churn probability P(Churn) for all 93,358 customers and compute:
     - risk_tier: High (>= 0.70), Medium (0.30-0.70), Low (< 0.30)
     - revenue_at_risk: P(Churn) * monetary_value (lifetime spend)
     - retention_priority: Decision Matrix (Priority 1 through 4 + Medium)
9. Write (upsert) predictions to ``ml.churn_predictions`` in PostgreSQL.
10. Emit an executive summary report to stdout.

Environment
-----------
Reads DATABASE_URL from .env (dotenv) or the process environment.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import create_engine, text

# Suppress benign SciPy/scikit-learn warnings during optimization
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

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
DEFAULT_ARTIFACT_PATH = REPO_ROOT / "ml" / "artifacts" / "churn_model.joblib"

# Risk tiers
RISK_TIER_HIGH = "High"
RISK_TIER_MEDIUM = "Medium"
RISK_TIER_LOW = "Low"

# Decision Matrix Priority Labels (docs/methodology.md §6)
PRIORITY_VIP = "Priority 1: Immediate VIP Retention"
PRIORITY_LOYALTY = "Priority 2: Loyalty & Nurture"
PRIORITY_REENGAGEMENT = "Priority 3: Automated Re-engagement"
PRIORITY_STANDARD = "Priority 4: Standard Operations"
PRIORITY_MEDIUM = "Medium Priority"

# Features selected for churn modeling (recency excluded to prevent target leakage)
NUMERIC_FEATURES = [
    "customer_lifespan_days",
    "lifetime_orders",
    "is_repeat_buyer",
    "lifetime_spend",
    "lifetime_product_spend",
    "lifetime_freight_spend",
    "freight_ratio",
    "avg_order_value",
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
    "f_score",
    "m_score",
]

CATEGORICAL_FEATURES = [
    "segment",
]

# ---------------------------------------------------------------------------
# DDL for Output Table
# ---------------------------------------------------------------------------
DDL_SCHEMA = "CREATE SCHEMA IF NOT EXISTS ml;"

DDL_TABLE = """
CREATE TABLE IF NOT EXISTS ml.churn_predictions (
    customer_unique_id      VARCHAR(50)     PRIMARY KEY,
    is_churned              SMALLINT        NOT NULL,  -- Observed label based on window cutoff
    churn_probability       NUMERIC(6, 4)   NOT NULL,  -- P(Churn) in [0.0000, 1.0000]
    risk_tier               VARCHAR(20)     NOT NULL,  -- 'High', 'Medium', 'Low'
    monetary_value          NUMERIC(12, 2)  NOT NULL,  -- Customer lifetime spend
    revenue_at_risk         NUMERIC(12, 2)  NOT NULL,  -- P(Churn) * monetary_value
    retention_priority      VARCHAR(50)     NOT NULL,  -- From Decision Matrix
    predicted_at            TIMESTAMPTZ     NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_churn_predictions_risk_tier
    ON ml.churn_predictions (risk_tier);
CREATE INDEX IF NOT EXISTS idx_churn_predictions_retention_priority
    ON ml.churn_predictions (retention_priority);
CREATE INDEX IF NOT EXISTS idx_churn_predictions_revenue_at_risk
    ON ml.churn_predictions (revenue_at_risk DESC);
"""

# ---------------------------------------------------------------------------
# SQL Queries
# ---------------------------------------------------------------------------
QUERY_METRICS = """
SELECT
    m.customer_unique_id,
    m.first_purchased_at,
    m.latest_purchased_at,
    m.recency_days,
    m.customer_lifespan_days,
    m.lifetime_orders,
    m.is_repeat_buyer,
    m.lifetime_spend,
    m.lifetime_product_spend,
    m.lifetime_freight_spend,
    m.avg_order_value,
    m.lifetime_items,
    m.avg_items_per_order,
    m.total_unique_products_purchased,
    m.total_unique_sellers_contacted,
    m.avg_delivery_delay_days,
    m.max_delivery_delay_days,
    m.late_orders_count,
    m.on_time_orders_count,
    m.late_order_ratio,
    m.has_late_delivery,
    m.total_reviews_submitted,
    m.avg_review_score,
    m.negative_reviews_count,
    m.positive_reviews_count,
    m.has_negative_review,
    m.negative_review_ratio,
    r.f_score,
    r.m_score,
    r.segment
FROM mart.mart_customer_metrics m
JOIN ml.rfm_segments r ON m.customer_unique_id = r.customer_unique_id
WHERE m.recency_days IS NOT NULL
  AND m.lifetime_spend IS NOT NULL;
"""

# ---------------------------------------------------------------------------
# Data Preparation & Feature Engineering
# ---------------------------------------------------------------------------


def load_dataset(database_url: str) -> pd.DataFrame:
    """Load customer metrics and RFM segments joined on customer_unique_id."""
    engine = create_engine(database_url)
    with engine.connect() as conn:
        df = pd.read_sql(text(QUERY_METRICS), conn)
    return df


def engineer_features(df: pd.DataFrame, window_days: int = 90) -> pd.DataFrame:
    """
    Engineer ML features and define time-bounded churn label.

    Parameters
    ----------
    df          : DataFrame with raw mart and RFM columns.
    window_days : Churn inactivity window in days (e.g. 90 or 180).

    Returns
    -------
    DataFrame with engineered features and 'is_churned' target column.
    """
    df = df.copy()

    # Time-bounded churn label
    df["is_churned"] = (df["recency_days"] > window_days).astype(int)

    # Boolean casting to integer flags
    df["is_repeat_buyer"] = df["is_repeat_buyer"].astype(int)
    df["has_late_delivery"] = df["has_late_delivery"].astype(int)
    df["has_negative_review"] = df["has_negative_review"].astype(int)

    # Derived interaction features
    df["freight_ratio"] = (df["lifetime_freight_spend"] / (df["lifetime_spend"] + 1e-5)).round(4)

    # Ensure segment is string and filled
    df["segment"] = df["segment"].fillna("Others").astype(str)

    return df


def create_preprocessor(
    numeric_features: Optional[List[str]] = None,
    categorical_features: Optional[List[str]] = None,
) -> ColumnTransformer:
    """Build scikit-learn ColumnTransformer for numeric and categorical pipelines."""
    num_cols = numeric_features if numeric_features is not None else NUMERIC_FEATURES
    cat_cols = categorical_features if categorical_features is not None else CATEGORICAL_FEATURES

    numeric_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_transformer = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="constant", fill_value="Others")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, num_cols),
            ("cat", categorical_transformer, cat_cols),
        ]
    )
    return preprocessor


# ---------------------------------------------------------------------------
# Business Logic Helpers (Risk Tier & Retention Priority)
# ---------------------------------------------------------------------------


def assign_risk_tier(prob: float) -> str:
    """
    Map churn probability P(Churn) to a risk tier:
      - High:   P >= 0.70
      - Medium: 0.30 <= P < 0.70
      - Low:    P < 0.30
    """
    if prob >= 0.70:
        return RISK_TIER_HIGH
    elif prob >= 0.30:
        return RISK_TIER_MEDIUM
    else:
        return RISK_TIER_LOW


def assign_retention_priority(churn_prob: float, m_score: int) -> str:
    """
    Map (churn_prob, m_score) to Priority Decision Matrix (docs/methodology.md §6).

    Matrix:
      - High Monetary (m_score >= 4) & High Churn (P >= 0.70) -> Priority 1: Immediate VIP Retention
      - High Monetary (m_score >= 4) & Low Churn  (P < 0.30)  -> Priority 2: Loyalty & Nurture
      - Low Monetary  (m_score <= 2) & High Churn (P >= 0.70) -> Priority 3: Automated Re-engagement
      - Low Monetary  (m_score <= 2) & Low Churn  (P < 0.30)  -> Priority 4: Standard Operations
      - All other combinations                                -> Medium Priority
    """
    if churn_prob >= 0.70 and m_score >= 4:
        return PRIORITY_VIP
    elif churn_prob < 0.30 and m_score >= 4:
        return PRIORITY_LOYALTY
    elif churn_prob >= 0.70 and m_score <= 2:
        return PRIORITY_REENGAGEMENT
    elif churn_prob < 0.30 and m_score <= 2:
        return PRIORITY_STANDARD
    else:
        return PRIORITY_MEDIUM


def compute_revenue_at_risk(churn_prob: float, monetary_value: float) -> float:
    """Expected Revenue at Risk = P(Churn) * monetary_value."""
    return round(float(churn_prob) * float(monetary_value), 2)


# ---------------------------------------------------------------------------
# Model Training & Evaluation
# ---------------------------------------------------------------------------


def evaluate_classifier(
    name: str,
    pipeline: Pipeline,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    top_k_ratio: float = 0.10,
) -> Dict[str, Any]:
    """Train pipeline and evaluate metrics on test set."""
    pipeline.fit(X_train, y_train)

    probs = pipeline.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.5).astype(int)

    auc = float(roc_auc_score(y_test, probs))
    pr_auc = float(average_precision_score(y_test, probs))
    f1 = float(f1_score(y_test, preds, zero_division=0))
    prec = float(precision_score(y_test, preds, zero_division=0))
    rec = float(recall_score(y_test, preds, zero_division=0))

    # Precision at Top K%
    k = max(1, int(top_k_ratio * len(y_test)))
    top_k_idx = np.argsort(probs)[-k:]
    p_at_k = float(y_test[top_k_idx].mean())

    return {
        "name": name,
        "pipeline": pipeline,
        "auc": round(auc, 4),
        "pr_auc": round(pr_auc, 4),
        "f1": round(f1, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "precision_at_k": round(p_at_k, 4),
    }


def train_candidate_models(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    preprocessor: ColumnTransformer,
) -> Tuple[str, Pipeline, List[Dict[str, Any]]]:
    """
    Train and evaluate candidate classifiers:
      1. Logistic Regression (Baseline)
      2. Random Forest Classifier
      3. HistGradientBoostingClassifier (LightGBM equivalent)

    Returns winning model name, fitted winning pipeline, and metrics list.
    """
    candidates = [
        (
            "Logistic Regression",
            LogisticRegression(max_iter=500, solver="liblinear", random_state=42),
        ),
        (
            "Random Forest",
            RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                random_state=42,
                n_jobs=-1,
            ),
        ),
        (
            "HistGradientBoosting",
            HistGradientBoostingClassifier(
                max_iter=100,
                max_depth=6,
                random_state=42,
            ),
        ),
    ]

    results: List[Dict[str, Any]] = []

    for name, clf in candidates:
        log.info("  Training candidate: %s ...", name)
        pipe = Pipeline(
            [
                ("preprocessor", preprocessor),
                ("classifier", clf),
            ]
        )
        metrics = evaluate_classifier(name, pipe, X_train, y_train, X_test, y_test)
        results.append(metrics)
        log.info(
            "    -> ROC-AUC: %.4f | F1: %.4f | Precision: %.4f | Recall: %.4f | P@10%%: %.4f",
            metrics["auc"],
            metrics["f1"],
            metrics["precision"],
            metrics["recall"],
            metrics["precision_at_k"],
        )

    # Select winner based on ROC-AUC
    best = max(results, key=lambda x: x["auc"])
    log.info("Winning model selected: %s (ROC-AUC: %.4f)", best["name"], best["auc"])
    return best["name"], best["pipeline"], results


# ---------------------------------------------------------------------------
# Database Persistence Helpers
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
    log.info("ml.churn_predictions table and indexes ready.")


def _upsert_predictions(conn, df: pd.DataFrame) -> int:
    """Upsert churn prediction rows using INSERT ... ON CONFLICT DO UPDATE."""
    upsert_sql = """
    INSERT INTO ml.churn_predictions (
        customer_unique_id, is_churned, churn_probability, risk_tier,
        monetary_value, revenue_at_risk, retention_priority, predicted_at
    ) VALUES %s
    ON CONFLICT (customer_unique_id) DO UPDATE SET
        is_churned          = EXCLUDED.is_churned,
        churn_probability   = EXCLUDED.churn_probability,
        risk_tier           = EXCLUDED.risk_tier,
        monetary_value      = EXCLUDED.monetary_value,
        revenue_at_risk     = EXCLUDED.revenue_at_risk,
        retention_priority  = EXCLUDED.retention_priority,
        predicted_at        = now();
    """
    now = pd.Timestamp.utcnow()
    records = [
        (
            row.customer_unique_id,
            int(row.is_churned),
            round(float(row.churn_probability), 4),
            row.risk_tier,
            round(float(row.monetary_value), 2),
            round(float(row.revenue_at_risk), 2),
            row.retention_priority,
            now,
        )
        for row in df.itertuples(index=False)
    ]
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, upsert_sql, records, page_size=2000)
    conn.commit()
    return len(records)


# ---------------------------------------------------------------------------
# Artifact Serialization
# ---------------------------------------------------------------------------


def save_model_artifact(
    artifact_data: Dict[str, Any],
    output_path: Path = DEFAULT_ARTIFACT_PATH,
) -> None:
    """Serialize the trained pipeline and metadata using joblib."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact_data, output_path)
    log.info("Saved model artifact to: %s", output_path)


def load_model_artifact(
    input_path: Path = DEFAULT_ARTIFACT_PATH,
) -> Dict[str, Any]:
    """Load serialized model artifact from disk."""
    if not input_path.exists():
        raise FileNotFoundError(f"Model artifact not found at {input_path}")
    return joblib.load(input_path)


# ---------------------------------------------------------------------------
# Full Pipeline Execution
# ---------------------------------------------------------------------------


def run_churn_pipeline(
    database_url: str,
    window_days: int = 90,
    model_choice: str = "best",
    dry_run: bool = False,
    artifact_path: Optional[Path] = DEFAULT_ARTIFACT_PATH,
) -> Tuple[pd.DataFrame, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Execute full Churn & Revenue-at-Risk pipeline.

    Returns
    -------
    df_scored    : DataFrame containing all 93,358 customer predictions.
    eval_results : Evaluation metrics for each candidate model.
    summary      : Aggregated metrics and revenue at risk statistics.
    """
    log.info("Loading mart and RFM data from database ...")
    df = load_dataset(database_url)
    log.info("  Loaded %s customer records.", f"{len(df):,}")

    log.info("Engineering features and churn labels (window=%d days) ...", window_days)
    df = engineer_features(df, window_days=window_days)
    churn_rate = df["is_churned"].mean()
    log.info("  Overall churn rate at %d days: %.2f%%", window_days, churn_rate * 100)

    # Feature matrix X and target y
    feature_cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    X = df[feature_cols]
    y = df["is_churned"].values

    # Train / test split: Stratified 80/20 split
    log.info("Splitting dataset into train (80%%) and test (20%%) stratified cohorts ...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    log.info("  Train samples: %s | Test samples: %s", f"{len(X_train):,}", f"{len(X_test):,}")

    # Build preprocessor
    preprocessor = create_preprocessor(NUMERIC_FEATURES, CATEGORICAL_FEATURES)

    # Train candidate models
    log.info("Training candidate classifiers ...")
    best_name, best_pipe, eval_results = train_candidate_models(
        X_train, y_train, X_test, y_test, preprocessor
    )

    # Allow overriding model if explicitly requested
    active_pipe = best_pipe
    active_name = best_name
    if model_choice != "best":
        matched = [
            r for r in eval_results if model_choice.lower() in r["name"].lower().replace(" ", "_")
        ]
        if matched:
            active_pipe = matched[0]["pipeline"]
            active_name = matched[0]["name"]
            log.info("Using user-requested model override: %s", active_name)

    # Save artifact
    if not dry_run and artifact_path is not None:
        artifact = {
            "model_name": active_name,
            "pipeline": active_pipe,
            "features": {
                "numeric": NUMERIC_FEATURES,
                "categorical": CATEGORICAL_FEATURES,
            },
            "eval_results": eval_results,
            "window_days": window_days,
            "trained_at": pd.Timestamp.utcnow().isoformat(),
        }
        save_model_artifact(artifact, artifact_path)

    # Generate predictions across full customer base
    log.info("Generating churn probabilities across full customer base (%s) ...", active_name)
    probs = active_pipe.predict_proba(X)[:, 1]
    df["churn_probability"] = probs.round(4)
    df["risk_tier"] = [assign_risk_tier(p) for p in df["churn_probability"]]
    df["monetary_value"] = df["lifetime_spend"].round(2)
    df["revenue_at_risk"] = [
        compute_revenue_at_risk(p, m) for p, m in zip(df["churn_probability"], df["monetary_value"])
    ]
    df["retention_priority"] = [
        assign_retention_priority(p, m) for p, m in zip(df["churn_probability"], df["m_score"])
    ]

    # Database write
    if not dry_run:
        log.info("Connecting to database for persistence ...")
        conn = _get_connection(database_url)
        try:
            _ensure_table(conn)
            written = _upsert_predictions(conn, df)
            log.info("  Successfully upserted %s rows into ml.churn_predictions.", f"{written:,}")
        finally:
            conn.close()
    else:
        log.info("  [DRY RUN] Skipping database upsert.")

    # Executive Summary statistics
    total_rev_at_risk = df["revenue_at_risk"].sum()
    total_historical_rev = df["monetary_value"].sum()
    summary = {
        "total_customers": len(df),
        "churn_window_days": window_days,
        "observed_churn_rate": churn_rate,
        "winning_model": active_name,
        "total_revenue_at_risk": total_rev_at_risk,
        "total_historical_spend": total_historical_rev,
        "revenue_at_risk_pct": (total_rev_at_risk / total_historical_rev * 100)
        if total_historical_rev
        else 0.0,
    }

    return df, eval_results, summary


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_summary(
    df: pd.DataFrame,
    eval_results: List[Dict[str, Any]],
    summary: Dict[str, Any],
) -> None:
    """Print clean executive summary and model scorecard."""
    print("\n" + "=" * 78)
    print("  Mercury Churn Prediction & Revenue-at-Risk Scorecard")
    print("=" * 78)

    # Model evaluation comparison table
    print("\n1. Candidate Model Performance (Test Cohort)")
    print("-" * 78)
    print(
        f"{'Model':<24} | {'ROC-AUC':<8} | {'PR-AUC':<8} | {'F1':<6} | {'Prec':<6} | {'Rec':<6} | {'P@10%':<6}"
    )
    print("-" * 78)
    for r in eval_results:
        print(
            f"{r['name']:<24} | {r['auc']:<8.4f} | {r['pr_auc']:<8.4f} | {r['f1']:<6.4f} | "
            f"{r['precision']:<6.4f} | {r['recall']:<6.4f} | {r['precision_at_k']:<6.4f}"
        )
    print("-" * 78)
    print(f"Selected Best Model: {summary['winning_model']}")

    # Churn Risk Tier Breakdown
    print("\n2. Customer Churn Risk Distribution")
    print("-" * 78)
    tier_stats = (
        df.groupby("risk_tier")
        .agg(
            customers=("customer_unique_id", "count"),
            avg_prob=("churn_probability", "mean"),
            total_rev_risk=("revenue_at_risk", "sum"),
            avg_spend=("monetary_value", "mean"),
        )
        .reindex([RISK_TIER_HIGH, RISK_TIER_MEDIUM, RISK_TIER_LOW])
    )
    tier_stats["pct_customers"] = (tier_stats["customers"] / len(df) * 100).round(1)
    tier_stats["pct_rev_risk"] = (
        tier_stats["total_rev_risk"] / summary["total_revenue_at_risk"] * 100
    ).round(1)

    print(
        f"{'Risk Tier':<10} | {'Customers':<10} | {'% Base':<8} | {'Avg P(Churn)':<14} | "
        f"{'Revenue at Risk (R$)':<22} | {'% Risk'}"
    )
    print("-" * 78)
    for tier, row in tier_stats.iterrows():
        print(
            f"{tier:<10} | {int(row['customers']):<10,d} | {row['pct_customers']:<7.1f}% | "
            f"{row['avg_prob']:<14.4f} | R$ {row['total_rev_risk']:<19,.2f} | {row['pct_rev_risk']:.1f}%"
        )
    print("-" * 78)

    # Priority Decision Matrix Breakdown
    print("\n3. Retention Priority Decision Matrix")
    print("-" * 78)
    prio_stats = (
        df.groupby("retention_priority")
        .agg(
            customers=("customer_unique_id", "count"),
            avg_prob=("churn_probability", "mean"),
            total_rev_risk=("revenue_at_risk", "sum"),
        )
        .sort_values("total_rev_risk", ascending=False)
    )
    prio_stats["pct_customers"] = (prio_stats["customers"] / len(df) * 100).round(1)

    print(
        f"{'Retention Action':<36} | {'Customers':<10} | {'Avg P(Churn)':<14} | {'Revenue at Risk (R$)'}"
    )
    print("-" * 78)
    for prio, row in prio_stats.iterrows():
        print(
            f"{prio:<36} | {int(row['customers']):<10,d} | {row['avg_prob']:<14.4f} | R$ {row['total_rev_risk']:,.2f}"
        )
    print("-" * 78)

    # Financial Bottom Line
    print("\n4. Financial Impact Summary")
    print("-" * 78)
    print(f"  Total Active/Scored Customers : {summary['total_customers']:,}")
    print(f"  Observation Window            : {summary['churn_window_days']} days")
    print(f"  Observed Churn Rate           : {summary['observed_churn_rate']:.2%}")
    print(f"  Total Historical Revenue      : R$ {summary['total_historical_spend']:,.2f}")
    print(
        f"  Total Expected Revenue at Risk: R$ {summary['total_revenue_at_risk']:,.2f} ({summary['revenue_at_risk_pct']:.1f}%)"
    )
    print("=" * 78 + "\n")


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mercury Churn Prediction & Revenue-at-Risk ML Engine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--window",
        type=int,
        default=90,
        help="Inactivity window in days to define churn label (e.g. 90 or 180).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="best",
        choices=["best", "hist_gradient_boosting", "random_forest", "logistic_regression"],
        help="Classifier selection override.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Train and evaluate without saving artifacts or writing to PostgreSQL.",
    )
    parser.add_argument(
        "--save-model",
        type=Path,
        default=DEFAULT_ARTIFACT_PATH,
        help="Output path for serialized joblib model artifact.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env",
        help="Path to .env file containing DATABASE_URL.",
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
        "Starting Churn ML pipeline (window=%d days, model=%s, dry_run=%s) ...",
        args.window,
        args.model,
        args.dry_run,
    )

    df_scored, eval_results, summary = run_churn_pipeline(
        database_url=database_url,
        window_days=args.window,
        model_choice=args.model,
        dry_run=args.dry_run,
        artifact_path=args.save_model if not args.dry_run else None,
    )

    print_summary(df_scored, eval_results, summary)
    log.info("Phase 6 ML execution complete.")


if __name__ == "__main__":
    main()
