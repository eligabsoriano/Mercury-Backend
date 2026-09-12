"""
backend/routers package
=======================
API route handlers for Mercury application.
"""

from backend.routers.analytics import router as analytics_router
from backend.routers.auth import auth_router
from backend.routers.customers import router as customers_router
from backend.routers.health import router as health_router
from backend.routers.predictions import router as predictions_router
from backend.routers.products import router as products_router
from backend.routers.sellers import router as sellers_router

__all__ = [
    "health_router",
    "analytics_router",
    "customers_router",
    "products_router",
    "sellers_router",
    "auth_router",
    "predictions_router",
]
