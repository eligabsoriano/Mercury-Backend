"""
backend/routers/health.py
=========================
Health check and diagnostic endpoints for monitoring and orchestrators.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import check_db_connection, get_db
from backend.schemas.common import HealthResponse
from backend.schemas.pipeline import PipelineHealthResponse
from backend.services.pipeline_service import pipeline_service

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health", response_model=HealthResponse, summary="System health check")
@router.get("/api/health", response_model=HealthResponse, summary="API system health check")
def health_check() -> HealthResponse:
    """
    Check API service status, environment details, and live PostgreSQL connectivity.
    """
    db_status = check_db_connection()
    status = "ok" if db_status["connected"] else "degraded"

    return HealthResponse(
        status=status,
        app_name=settings.app_name,
        version=settings.app_version,
        database=db_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/api/health/pipeline",
    response_model=PipelineHealthResponse,
    summary="Data pipeline and ML model health check",
)
def pipeline_health(db: Session = Depends(get_db)) -> PipelineHealthResponse:
    """
    Evaluate end-to-end data pipeline freshness, table counts across schemas,
    ML model artifact status, and operational anomalies.
    """
    return pipeline_service.get_pipeline_health(db)
