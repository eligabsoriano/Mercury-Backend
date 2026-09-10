"""
backend/schemas/common.py
=========================
Common reusable Pydantic schemas for pagination, health checks, and metadata.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Generic, List, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata included in paginated list responses."""

    model_config = ConfigDict(from_attributes=True)

    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, le=100, description="Number of items per page")
    total_items: int = Field(..., ge=0, description="Total matching items across all pages")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

    @classmethod
    def create(cls, page: int, page_size: int, total_items: int) -> "PaginationMeta":
        total_pages = math.ceil(total_items / page_size) if page_size > 0 else 0
        return cls(
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic envelope for paginated resource lists."""

    model_config = ConfigDict(from_attributes=True)

    items: List[T] = Field(..., description="List of items for the current page")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class HealthResponse(BaseModel):
    """System health check and diagnostic information."""

    model_config = ConfigDict(from_attributes=True)

    status: str = Field(..., description="Overall system status (ok / degraded)")
    app_name: str = Field(..., description="API service name")
    version: str = Field(..., description="Current service release version")
    database: Dict[str, Any] = Field(..., description="Database connectivity status and latency")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of check")
