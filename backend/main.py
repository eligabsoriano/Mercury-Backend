"""
backend/main.py
===============
FastAPI Application Entrypoint for Mercury Customer Intelligence Platform.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.database import check_db_connection
from backend.routers import analytics_router, customers_router, health_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("mercury.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager to check dependencies on startup."""
    log.info("Starting %s v%s (%s)", settings.app_name, settings.app_version, settings.env)
    db_check = check_db_connection()
    if db_check["connected"]:
        log.info("PostgreSQL database connection verified (latency: %.2f ms)", db_check["latency_ms"])
    else:
        log.warning("Database connection warning: %s", db_check["error"])
    yield
    log.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "Analytics",
            "description": "Macro-level portfolio KPIs, RFM segment breakdowns, and revenue-at-risk exposure.",
        },
        {
            "name": "Customers",
            "description": "Paginated customer listings, multi-faceted filters, at-risk queues, and 360-degree profiles.",
        },
        {
            "name": "Health",
            "description": "System health and database connectivity diagnostics.",
        },
    ],
)

# Configure Cross-Origin Resource Sharing (CORS) for web and mobile clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(health_router)
app.include_router(analytics_router)
app.include_router(customers_router)


@app.get("/", summary="API Root & Navigation Index", tags=["Health"])
def root_index() -> JSONResponse:
    """Returns basic API service metadata and documentation links."""
    return JSONResponse(
        content={
            "app_name": settings.app_name,
            "version": settings.app_version,
            "status": "online",
            "documentation": {
                "swagger_ui": "/docs",
                "redoc": "/redoc",
                "openapi_spec": "/openapi.json",
            },
            "endpoints": {
                "health": "/health",
                "portfolio_overview": "/api/analytics/overview",
                "rfm_segments": "/api/analytics/segments",
                "revenue_at_risk": "/api/analytics/revenue-at-risk",
                "customers": "/api/customers",
                "at_risk_queue": "/api/customers/at-risk",
            },
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
    )
