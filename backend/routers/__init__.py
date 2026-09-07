"""
backend/routers package
=======================
API route handlers for Mercury application.
"""

from backend.routers.analytics import router as analytics_router
from backend.routers.customers import router as customers_router
from backend.routers.health import router as health_router

__all__ = [
    "health_router",
    "analytics_router",
    "customers_router",
]
