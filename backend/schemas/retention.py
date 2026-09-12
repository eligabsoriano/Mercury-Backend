"""
backend/schemas/retention.py
============================
Pydantic v2 models for prescriptive retention playbooks, campaign ROI simulation,
optimal budget allocation, and customer-level retention recommendations.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class RetentionPlaybook(BaseModel):
    """Cataloged prescriptive retention action playbook."""

    playbook_id: str = Field(..., description="Unique playbook identifier slug")
    name: str = Field(..., description="Human-readable playbook name")
    description: str = Field(..., description="Operational summary and objective")
    target_criteria: str = Field(..., description="Target segment, risk tier, or friction trigger")
    intervention_channel: str = Field(
        ..., description="Outreach channel (e.g. Phone/Concierge, Email, WhatsApp, In-App)"
    )
    recommended_action: str = Field(..., description="Specific business intervention prescribed")
    default_cost_per_customer: float = Field(
        ..., ge=0.0, description="Estimated unit cost per customer in BRL"
    )
    estimated_save_rate_min: float = Field(
        ..., ge=0.0, le=1.0, description="Conservative expected customer save rate"
    )
    estimated_save_rate_max: float = Field(
        ..., ge=0.0, le=1.0, description="Optimistic expected customer save rate"
    )
    action_template: str = Field(..., description="Sample communication or outreach script")


class CampaignSimulationRequest(BaseModel):
    """
    Request schema for simulating retention campaign financial economics.
    Supply explicit volume/revenue metrics, or target specific customer IDs / playbooks.
    """

    playbook_id: Optional[str] = Field(
        None, description="Optional playbook ID to pre-populate default costs and save rates"
    )
    target_customer_count: int = Field(
        ..., ge=1, description="Number of at-risk customers targeted by the campaign"
    )
    target_revenue_at_risk: float = Field(
        ...,
        ge=0.0,
        description="Total portfolio revenue at risk represented by targeted customers (BRL)",
    )
    cost_per_customer: float = Field(
        ...,
        ge=0.0,
        description="Cost of the intervention per targeted customer in BRL (discounts, outreach)",
    )
    expected_save_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated fraction of targeted customers successfully retained (e.g. 0.25 = 25%)",
    )
    customer_unique_ids: Optional[List[str]] = Field(
        None, description="Optional explicit customer IDs targeted"
    )


class CampaignSimulationResult(BaseModel):
    """Financial output metrics for a simulated retention campaign."""

    playbook_id: Optional[str] = Field(None, description="Playbook ID if specified")
    target_customer_count: int = Field(..., description="Total customers targeted")
    total_campaign_cost: float = Field(..., description="Total cost of campaign execution (BRL)")
    target_revenue_at_risk: float = Field(..., description="Gross revenue at risk targeted (BRL)")
    projected_customers_saved: int = Field(
        ..., description="Estimated number of customers retained"
    )
    gross_revenue_saved: float = Field(
        ...,
        description="Gross revenue protected = target_revenue_at_risk * expected_save_rate (BRL)",
    )
    net_saved_value: float = Field(
        ..., description="Net economic gain = gross_revenue_saved - total_campaign_cost (BRL)"
    )
    roi_percentage: float = Field(
        ..., description="Return on Investment = (net_saved_value / total_campaign_cost) * 100"
    )
    break_even_save_rate: float = Field(
        ...,
        description="Minimum save rate required for the campaign to break even (net value = 0)",
    )
    capital_efficiency_multiplier: float = Field(
        ..., description="Efficiency ratio = gross_revenue_saved / total_campaign_cost"
    )
    is_profitable: bool = Field(..., description="True if projected net value > 0")
    recommendation: str = Field(
        ..., description="Strategic executive recommendation based on ROI and break-even"
    )


class CandidatePoolInput(BaseModel):
    """Candidate customer segment or playbook pool for budget optimization."""

    pool_name: str = Field(..., description="Identifier name for this customer pool")
    playbook_id: str = Field(..., description="Playbook applied to this pool")
    available_customers: int = Field(..., ge=1, description="Total eligible customers in pool")
    total_revenue_at_risk: float = Field(
        ..., ge=0.0, description="Total revenue at risk for pool (BRL)"
    )
    cost_per_customer: float = Field(
        ..., ge=0.0, description="Cost per customer intervention (BRL)"
    )
    expected_save_rate: float = Field(..., ge=0.0, le=1.0, description="Expected retention rate")


class PoolAllocation(BaseModel):
    """Allocated spend and projected return for an individual pool."""

    pool_name: str = Field(..., description="Customer pool name")
    playbook_id: str = Field(..., description="Playbook ID")
    customers_targeted: int = Field(..., description="Number of customers funded in this pool")
    max_available_customers: int = Field(..., description="Total available customers in pool")
    coverage_ratio: float = Field(
        ..., description="Fraction of pool funded (customers_targeted / max)"
    )
    allocated_spend: float = Field(..., description="Budget allocated to this pool (BRL)")
    gross_revenue_saved: float = Field(..., description="Projected gross revenue saved (BRL)")
    net_value: float = Field(..., description="Projected net gain (BRL)")
    pool_roi: float = Field(..., description="Projected pool ROI percentage")
    marginal_efficiency: float = Field(..., description="Revenue saved per BRL spent")


class BudgetAllocationRequest(BaseModel):
    """Request schema for optimizing capital deployment across candidate retention pools."""

    total_budget: float = Field(..., ge=1.0, description="Total capital available to deploy in BRL")
    candidate_pools: Optional[List[CandidatePoolInput]] = Field(
        None,
        description="Optional list of custom pools. If omitted, pools are dynamically hydrated from live database marts.",
    )


class BudgetAllocationResult(BaseModel):
    """Optimal portfolio budget allocation maximizing net saved revenue."""

    total_budget: float = Field(..., description="Total budget input (BRL)")
    allocated_budget: float = Field(..., description="Total budget successfully deployed (BRL)")
    remaining_budget: float = Field(..., description="Unspent budget (BRL)")
    total_customers_targeted: int = Field(
        ..., description="Total customers reached across all pools"
    )
    total_gross_recovered: float = Field(..., description="Total gross revenue protected (BRL)")
    total_net_value: float = Field(
        ..., description="Portfolio net value = gross_recovered - allocated (BRL)"
    )
    portfolio_roi: float = Field(..., description="Overall portfolio ROI percentage")
    portfolio_efficiency: float = Field(
        ..., description="Overall gross revenue saved per BRL spent"
    )
    allocations: List[PoolAllocation] = Field(..., description="Pool-by-pool allocation breakdown")


class CustomerPlaybookRecommendation(BaseModel):
    """Prescriptive playbook recommendation tailored to a specific customer's churn friction."""

    customer_unique_id: str = Field(..., description="Unique customer ID")
    churn_probability: float = Field(..., description="Customer churn probability")
    risk_tier: str = Field(..., description="Customer risk tier")
    revenue_at_risk: float = Field(..., description="Customer financial exposure (BRL)")
    primary_friction: str = Field(..., description="Identified primary churn root cause")
    recommended_playbook: RetentionPlaybook = Field(
        ..., description="Top recommended intervention playbook"
    )
    expected_gross_recovery: float = Field(
        ..., description="Expected revenue saved from intervention"
    )
    projected_net_gain: float = Field(..., description="Expected net gain after playbook cost")
    suggested_message: str = Field(..., description="Personalized outreach message template")
