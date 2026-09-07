"""
backend/routers/health.py
=========================
Health check and diagnostic endpoints for monitoring and orchestrators.
"""

from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter

from backend.config import get_settings
from backend.database import check_db_connection
from backend.schemas.common import HealthResponse

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
