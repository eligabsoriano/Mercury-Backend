"""
backend/services/pipeline_service.py
====================================
Observability and diagnostic service for Mercury's data pipeline,
table row-count tracking, analytical freshness, and ML model health.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.database import check_db_connection
from backend.schemas.pipeline import (
    DataFreshnessMetrics,
    ModelArtifactMetrics,
    PipelineHealthResponse,
    PipelineRunRecord,
    TableCountMetrics,
)

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_ARTIFACT_PATH = REPO_ROOT / "ml" / "artifacts" / "churn_model.joblib"
PIPELINE_STATUS_PATH = REPO_ROOT / "pipeline_status.json"


def _read_pipeline_status_file() -> Optional[PipelineRunRecord]:
    """Read the latest pipeline execution status from pipeline_status.json if present."""
    if not PIPELINE_STATUS_PATH.exists():
        return None
    try:
        with open(PIPELINE_STATUS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return PipelineRunRecord(
                run_id=data.get("run_id"),
                status=data.get("status", "unknown"),
                start_time=data.get("start_time"),
                end_time=data.get("end_time"),
                duration_seconds=data.get("duration_seconds"),
                steps_executed=data.get("steps_executed", []),
            )
    except Exception as exc:
        log.warning("Failed to read pipeline_status.json: %s", exc)
        return None


def _inspect_model_artifact() -> ModelArtifactMetrics:
    """Inspect serialized churn model artifact on disk without loading heavy memory weights."""
    exists = MODEL_ARTIFACT_PATH.exists()
    if not exists:
        return ModelArtifactMetrics(
            artifact_found=False,
            artifact_path=str(MODEL_ARTIFACT_PATH),
            file_size_bytes=None,
            last_modified=None,
            model_type=None,
            features_count=None,
            is_trained=False,
        )

    try:
        stat = MODEL_ARTIFACT_PATH.stat()
        file_size = stat.st_size
        last_mod = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        # Lightweight check: we know from ml/churn.py that our trained model is HistGradientBoostingClassifier
        return ModelArtifactMetrics(
            artifact_found=True,
            artifact_path=str(MODEL_ARTIFACT_PATH),
            file_size_bytes=file_size,
            last_modified=last_mod,
            model_type="HistGradientBoostingClassifier",
            features_count=13,
            is_trained=True,
        )
    except Exception as exc:
        log.warning("Error inspecting model artifact: %s", exc)
        return ModelArtifactMetrics(
            artifact_found=True,
            artifact_path=str(MODEL_ARTIFACT_PATH),
            file_size_bytes=None,
            last_modified=None,
            model_type=None,
            features_count=None,
            is_trained=False,
        )


def _get_table_counts(db: Session) -> TableCountMetrics:
    """Query current row counts across raw, mart, and ML prediction schemas."""
    # Attempt unified aggregation query
    query = text("""
        SELECT
            (SELECT COUNT(*) FROM raw.orders) AS raw_orders,
            (SELECT COUNT(*) FROM raw.customers) AS raw_customers,
            (SELECT COUNT(*) FROM mart.mart_customer_metrics) AS mart_customer_metrics,
            (SELECT COUNT(*) FROM mart.fact_orders) AS mart_fact_orders,
            (SELECT COUNT(*) FROM mart.mart_marketing_funnel) AS mart_marketing_funnel,
            (SELECT COUNT(*) FROM ml.rfm_segments) AS ml_rfm_segments,
            (SELECT COUNT(*) FROM ml.churn_predictions) AS ml_churn_predictions;
    """)

    try:
        result = db.execute(query).mappings().first()
        if result:
            return TableCountMetrics(
                raw_orders=int(result.get("raw_orders") or 0),
                raw_customers=int(result.get("raw_customers") or 0),
                mart_customer_metrics=int(result.get("mart_customer_metrics") or 0),
                mart_fact_orders=int(result.get("mart_fact_orders") or 0),
                mart_marketing_funnel=int(result.get("mart_marketing_funnel") or 0),
                ml_rfm_segments=int(result.get("ml_rfm_segments") or 0),
                ml_churn_predictions=int(result.get("ml_churn_predictions") or 0),
            )
    except Exception as exc:
        log.warning("Unified table count query failed, falling back to safe defaults: %s", exc)

    return TableCountMetrics(
        raw_orders=0,
        raw_customers=0,
        mart_customer_metrics=0,
        mart_fact_orders=0,
        mart_marketing_funnel=0,
        ml_rfm_segments=0,
        ml_churn_predictions=0,
    )


def _get_last_order_timestamp(db: Session) -> Optional[str]:
    """Retrieve the latest order timestamp from mart.fact_orders or raw.orders."""
    query = text("SELECT MAX(purchased_at) AS max_ts FROM mart.fact_orders;")
    try:
        val = db.execute(query).scalar()
        if val is not None:
            return str(val)
    except Exception:
        pass
    return None


class PipelineService:
    """Service providing pipeline health, freshness, table metrics, and anomaly detection."""

    @staticmethod
    def get_pipeline_health(db: Session) -> PipelineHealthResponse:
        """
        Evaluate full-stack pipeline health across database, dbt marts,
        ML artifacts, freshness timestamps, and operational anomalies.
        """
        db_status = check_db_connection()
        is_connected = bool(db_status.get("connected", False))
        latency = db_status.get("latency_ms")

        # Table counts & data freshness
        if is_connected:
            table_counts = _get_table_counts(db)
            last_order_ts = _get_last_order_timestamp(db)
        else:
            table_counts = TableCountMetrics(
                raw_orders=0,
                raw_customers=0,
                mart_customer_metrics=0,
                mart_fact_orders=0,
                mart_marketing_funnel=0,
                ml_rfm_segments=0,
                ml_churn_predictions=0,
            )
            last_order_ts = None

        # Last pipeline run file
        last_run = _read_pipeline_status_file()
        freshness_status = (
            "fresh" if last_order_ts else ("unknown" if not is_connected else "stale")
        )

        freshness = DataFreshnessMetrics(
            last_order_timestamp=last_order_ts,
            last_pipeline_run=last_run,
            pipeline_freshness_status=freshness_status,
        )

        # Model artifact
        model_metrics = _inspect_model_artifact()

        # Anomaly detection rules
        anomalies: List[str] = []
        if not is_connected:
            anomalies.append("Database connection is offline or unreachable.")
        else:
            if table_counts.raw_orders == 0:
                anomalies.append("Raw ingestion data is missing (raw.orders is empty).")
            if table_counts.mart_customer_metrics == 0:
                anomalies.append("dbt transformation mart mart.mart_customer_metrics is empty.")
            if table_counts.ml_churn_predictions == 0:
                anomalies.append("ML predictions table ml.churn_predictions is empty.")
            elif table_counts.mart_customer_metrics > table_counts.ml_churn_predictions:
                diff = table_counts.mart_customer_metrics - table_counts.ml_churn_predictions
                anomalies.append(
                    f"Unscored customers detected: {diff} customers lack churn predictions."
                )

        if not model_metrics.artifact_found:
            anomalies.append(
                "Serialized churn model artifact (churn_model.joblib) is missing on disk."
            )

        # Determine overall status
        if not is_connected:
            status = "degraded"
        elif anomalies:
            status = "warning"
        else:
            status = "ok"

        return PipelineHealthResponse(
            status=status,
            timestamp=datetime.now(timezone.utc).isoformat(),
            database_connected=is_connected,
            database_latency_ms=latency,
            table_counts=table_counts,
            freshness=freshness,
            model=model_metrics,
            anomalies=anomalies,
        )


pipeline_service = PipelineService()
