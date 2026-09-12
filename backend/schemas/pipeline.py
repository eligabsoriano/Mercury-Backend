"""
backend/schemas/pipeline.py
==========================
Pydantic v2 request/response schemas for data pipeline observability,
table row counts, data freshness timestamps, and ML model health.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class TableCountMetrics(BaseModel):
    """Row count metrics across raw, analytics mart, and ML prediction schemas."""

    model_config = ConfigDict(from_attributes=True)

    raw_orders: int = Field(..., ge=0, description="Row count in raw.orders")
    raw_customers: int = Field(..., ge=0, description="Row count in raw.customers")
    mart_customer_metrics: int = Field(
        ..., ge=0, description="Row count in mart.mart_customer_metrics"
    )
    mart_fact_orders: int = Field(..., ge=0, description="Row count in mart.fact_orders")
    mart_marketing_funnel: int = Field(
        ..., ge=0, description="Row count in mart.mart_marketing_funnel"
    )
    ml_rfm_segments: int = Field(..., ge=0, description="Row count in ml.rfm_segments")
    ml_churn_predictions: int = Field(..., ge=0, description="Row count in ml.churn_predictions")


class PipelineRunRecord(BaseModel):
    """Summary metadata of the most recent pipeline execution."""

    model_config = ConfigDict(from_attributes=True)

    run_id: Optional[str] = Field(None, description="Unique execution run ID")
    status: str = Field(..., description="Run status (success / failed / partial)")
    start_time: Optional[str] = Field(None, description="Execution start timestamp")
    end_time: Optional[str] = Field(None, description="Execution completion timestamp")
    duration_seconds: Optional[float] = Field(
        None, ge=0, description="Total execution duration in seconds"
    )
    steps_executed: List[str] = Field(
        default_factory=list, description="List of pipeline steps executed"
    )


class DataFreshnessMetrics(BaseModel):
    """Data freshness and recency indicators across the analytical marts."""

    model_config = ConfigDict(from_attributes=True)

    last_order_timestamp: Optional[str] = Field(
        None, description="Most recent order purchase timestamp in the data mart"
    )
    last_pipeline_run: Optional[PipelineRunRecord] = Field(
        None, description="Metadata of the last orchestrator run"
    )
    pipeline_freshness_status: str = Field(
        ..., description="Freshness status (fresh / stale / unknown)"
    )


class ModelArtifactMetrics(BaseModel):
    """Status, metadata, and drift indicators for the churn ML model artifact."""

    model_config = ConfigDict(from_attributes=True)

    artifact_found: bool = Field(
        ..., description="Whether the serialized joblib model exists on disk"
    )
    artifact_path: str = Field(..., description="File path to the serialized model artifact")
    file_size_bytes: Optional[int] = Field(
        None, ge=0, description="Model artifact file size in bytes"
    )
    last_modified: Optional[str] = Field(
        None, description="ISO timestamp of last artifact modification"
    )
    model_type: Optional[str] = Field(None, description="Classifier algorithm class name")
    features_count: Optional[int] = Field(
        None, ge=0, description="Number of feature columns expected by the model"
    )
    is_trained: bool = Field(..., description="Whether the model is fitted and ready for inference")


class PipelineHealthResponse(BaseModel):
    """Consolidated pipeline observability, data freshness, and model diagnostic response."""

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(..., description="Overall pipeline health status (ok / warning / degraded)")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of the health check")
    database_connected: bool = Field(..., description="Whether the database connection is active")
    database_latency_ms: Optional[float] = Field(
        None, description="Database ping latency in milliseconds"
    )
    table_counts: TableCountMetrics = Field(
        ..., description="Current row counts across storage schemas"
    )
    freshness: DataFreshnessMetrics = Field(..., description="Data freshness and recency tracking")
    model: ModelArtifactMetrics = Field(
        ..., description="Model artifact storage and metadata status"
    )
    anomalies: List[str] = Field(
        default_factory=list, description="Detected pipeline anomalies, drift, or integrity alerts"
    )
