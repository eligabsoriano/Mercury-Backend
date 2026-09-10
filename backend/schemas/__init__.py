"""
backend/schemas package
=======================
Exposes all Pydantic v2 schemas for Mercury API.
"""

from backend.schemas.analytics import (
    PortfolioOverview,
    RevenueAtRiskOverview,
    SegmentsOverview,
)
from backend.schemas.auth import (
    TokenRequest,
    TokenResponse,
    UserIdentity,
)
from backend.schemas.churn import (
    ChurnPrediction,
    RetentionPrioritySummary,
    RiskTierSummary,
)
from backend.schemas.common import (
    HealthResponse,
    PaginatedResponse,
    PaginationMeta,
)
from backend.schemas.customer import (
    CustomerBasketMetrics,
    CustomerDetail,
    CustomerFulfillmentMetrics,
    CustomerListResponse,
    CustomerReviewMetrics,
    CustomerSummary,
)
from backend.schemas.rfm import (
    RFMScorecard,
    SegmentDistribution,
)

__all__ = [
    "PaginationMeta",
    "PaginatedResponse",
    "HealthResponse",
    "RFMScorecard",
    "SegmentDistribution",
    "ChurnPrediction",
    "RiskTierSummary",
    "RetentionPrioritySummary",
    "CustomerBasketMetrics",
    "CustomerFulfillmentMetrics",
    "CustomerReviewMetrics",
    "CustomerSummary",
    "CustomerDetail",
    "CustomerListResponse",
    "PortfolioOverview",
    "SegmentsOverview",
    "RevenueAtRiskOverview",
    "TokenRequest",
    "TokenResponse",
    "UserIdentity",
]
