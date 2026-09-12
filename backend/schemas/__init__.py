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
from backend.schemas.prediction import (
    ChurnPredictionInput,
    ChurnPredictionResult,
    CounterfactualSimulationRequest,
    CounterfactualSimulationResponse,
    FeatureContribution,
    ModelMetadataResponse,
)
from backend.schemas.retention import (
    BudgetAllocationRequest,
    BudgetAllocationResult,
    CampaignSimulationRequest,
    CampaignSimulationResult,
    CandidatePoolInput,
    CustomerPlaybookRecommendation,
    PoolAllocation,
    RetentionPlaybook,
)
from backend.schemas.rfm import (
    RFMScorecard,
    SegmentDistribution,
)

__all__ = [
    "PaginationMeta",
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
    "ChurnPredictionInput",
    "ChurnPredictionResult",
    "CounterfactualSimulationRequest",
    "CounterfactualSimulationResponse",
    "FeatureContribution",
    "ModelMetadataResponse",
    "RetentionPlaybook",
    "CampaignSimulationRequest",
    "CampaignSimulationResult",
    "CandidatePoolInput",
    "PoolAllocation",
    "BudgetAllocationRequest",
    "BudgetAllocationResult",
    "CustomerPlaybookRecommendation",
]
