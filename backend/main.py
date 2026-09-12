"""
backend/main.py
===============
FastAPI Application Entrypoint for Mercury Customer Intelligence Platform.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import get_settings
from backend.database import check_db_connection
from backend.middleware import RequestTracingAndSecurityMiddleware
from backend.routers import (
    analytics_router,
    auth_router,
    customers_router,
    health_router,
    marketing_router,
    predictions_router,
    products_router,
    retention_router,
    sellers_router,
)
from backend.security import verify_auth

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
        log.info(
            "PostgreSQL database connection verified (latency: %.2f ms)", db_check["latency_ms"]
        )
    else:
        log.warning("Database connection warning: %s", db_check["error"])
    yield
    log.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    lifespan=lifespan,
    dependencies=[Depends(verify_auth)],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Token grant, credential verification, and identity introspection.",
        },
        {
            "name": "Analytics",
            "description": "Macro-level portfolio KPIs, RFM segment breakdowns, and revenue-at-risk exposure.",
        },
        {
            "name": "Customers",
            "description": "Paginated customer listings, multi-faceted filters, at-risk queues, and 360-degree profiles.",
        },
        {
            "name": "Products",
            "description": "Product catalog intelligence, category breakdown, sales velocity, and review scores.",
        },
        {
            "name": "Sellers",
            "description": "Marketplace seller performance scorecards, delivery delay rates, and seller directories.",
        },
        {
            "name": "Predictions",
            "description": "Real-time ML churn scoring, counterfactual 'what-if' simulations, and model transparency.",
        },
        {
            "name": "Retention",
            "description": "Prescriptive playbooks, campaign financial simulations, and Knapsack budget optimization.",
        },
        {
            "name": "Marketing",
            "description": "Seller acquisition marketing funnel, sales cycle velocity, and origin channel attribution.",
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

# Attach request tracing, performance measurement, and rate limiting middleware
app.add_middleware(RequestTracingAndSecurityMiddleware)

# Register route modules
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(analytics_router)
app.include_router(customers_router)
app.include_router(predictions_router)
app.include_router(retention_router)
app.include_router(marketing_router)
app.include_router(products_router)
app.include_router(sellers_router)


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
                "auth_token": "/api/auth/token",
                "auth_identity": "/api/auth/me",
                "portfolio_overview": "/api/analytics/overview",
                "rfm_segments": "/api/analytics/segments",
                "revenue_at_risk": "/api/analytics/revenue-at-risk",
                "revenue_trends": "/api/analytics/revenue",
                "cohort_retention": "/api/analytics/retention",
                "customers": "/api/customers",
                "at_risk_queue": "/api/customers/at-risk",
                "customer_export": "/api/customers/export",
                "predict_churn": "/api/predictions/churn",
                "simulate_churn": "/api/predictions/churn/simulate",
                "model_info": "/api/predictions/model/info",
                "products": "/api/products",
                "product_categories": "/api/products/categories",
                "sellers": "/api/sellers",
                "retention_playbooks": "/api/retention/playbooks",
                "campaign_simulate_roi": "/api/retention/campaigns/simulate-roi",
                "campaign_optimize_budget": "/api/retention/campaigns/optimize-budget",
                "marketing_overview": "/api/marketing/overview",
                "marketing_channels": "/api/marketing/channels",
                "marketing_velocity": "/api/marketing/velocity",
                "marketing_segments": "/api/marketing/segments",
                "marketing_leads": "/api/marketing/leads",
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
