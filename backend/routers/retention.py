"""
backend/routers/retention.py
============================
REST API endpoints for prescriptive retention playbooks, campaign financial ROI
simulations, capital budget optimization, and customer intervention recommendations.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Body, Depends, Path
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.retention import (
    BudgetAllocationRequest,
    BudgetAllocationResult,
    CampaignSimulationRequest,
    CampaignSimulationResult,
    CustomerPlaybookRecommendation,
    RetentionPlaybook,
)
from backend.services.retention_service import RetentionService

router = APIRouter(prefix="/api/retention", tags=["Retention"])


def get_retention_service() -> RetentionService:
    """Dependency provider for RetentionService."""
    return RetentionService()


@router.get(
    "/playbooks",
    response_model=List[RetentionPlaybook],
    summary="List Prescriptive Retention Playbooks",
    description=(
        "Retrieve the complete catalog of prescriptive retention intervention playbooks, "
        "including target friction criteria, outreach channels, unit costs, expected save rates, "
        "and communication templates."
    ),
)
def list_playbooks(
    service: RetentionService = Depends(get_retention_service),
) -> List[RetentionPlaybook]:
    return service.get_playbooks()


@router.get(
    "/playbooks/{playbook_id}",
    response_model=RetentionPlaybook,
    summary="Get Retention Playbook by ID",
    description="Retrieve operational specifications for an individual retention playbook.",
)
def get_playbook(
    playbook_id: str = Path(
        ..., description="Unique playbook slug (e.g. vip_concierge, logistics_friction_recovery)"
    ),
    service: RetentionService = Depends(get_retention_service),
) -> RetentionPlaybook:
    return service.get_playbook(playbook_id)


@router.post(
    "/campaigns/simulate-roi",
    response_model=CampaignSimulationResult,
    summary="Simulate Campaign Financial ROI",
    description=(
        "Simulate the financial unit economics of a customer retention campaign. "
        "Computes gross revenue saved, total campaign execution costs, net economic gain, "
        "ROI percentage, break-even save rate, and an executive recommendation."
    ),
)
def simulate_campaign_roi(
    payload: CampaignSimulationRequest = Body(
        ...,
        description="Campaign parameters including target volume, revenue at risk, cost, and expected save rate",
        examples=[
            {
                "playbook_id": "vip_concierge",
                "target_customer_count": 500,
                "target_revenue_at_risk": 250000.0,
                "cost_per_customer": 45.0,
                "expected_save_rate": 0.35,
            }
        ],
    ),
    db: Session = Depends(get_db),
    service: RetentionService = Depends(get_retention_service),
) -> CampaignSimulationResult:
    return service.simulate_campaign(payload, db)


@router.post(
    "/campaigns/optimize-budget",
    response_model=BudgetAllocationResult,
    summary="Optimize Retention Budget Allocation",
    description=(
        "Solve the optimal capital deployment across candidate customer retention pools given a fixed budget. "
        "Maximizes portfolio recovered revenue by prioritizing pools with highest marginal capital efficiency."
    ),
)
def optimize_retention_budget(
    payload: BudgetAllocationRequest = Body(
        ...,
        description="Total budget available and optional candidate pool definitions",
        examples=[
            {
                "total_budget": 50000.0,
            }
        ],
    ),
    db: Session = Depends(get_db),
    service: RetentionService = Depends(get_retention_service),
) -> BudgetAllocationResult:
    return service.optimize_budget(payload, db)


@router.get(
    "/recommendations/{customer_unique_id}",
    response_model=CustomerPlaybookRecommendation,
    summary="Customer Prescriptive Playbook Recommendation",
    description=(
        "Diagnose primary churn root causes (logistics delays, review ratings, inactivity lapse) "
        "for an individual customer and prescribe the optimal retention playbook with expected net recovery."
    ),
)
def get_customer_retention_recommendation(
    customer_unique_id: str = Path(
        ..., description="Unique customer identifier (customer_unique_id)"
    ),
    db: Session = Depends(get_db),
    service: RetentionService = Depends(get_retention_service),
) -> CustomerPlaybookRecommendation:
    return service.recommend_for_customer(customer_unique_id, db)
