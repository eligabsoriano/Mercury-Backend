"""
backend/services/retention_service.py
=====================================
Prescriptive retention economics, decision playbooks, campaign financial simulation,
and capital-constrained budget optimization engine.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

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

log = logging.getLogger(__name__)


class RetentionService:
    """Service providing prescriptive retention analytics, playbooks, and ROI optimization."""

    PLAYBOOKS: Dict[str, RetentionPlaybook] = {
        "vip_concierge": RetentionPlaybook(
            playbook_id="vip_concierge",
            name="VIP Concierge & Dedicated Account Outreach",
            description="High-touch proactive outreach by senior account managers with custom compensation credit.",
            target_criteria="High-Value Customers (Champions & Loyal) with High Churn Risk (P >= 0.70)",
            intervention_channel="Direct Phone / Dedicated Account Manager",
            recommended_action="1-on-1 concierge consultation, R$ 100 compensation credit, and permanent priority fulfillment routing.",
            default_cost_per_customer=45.00,
            estimated_save_rate_min=0.28,
            estimated_save_rate_max=0.45,
            action_template=(
                "Hello {customer_name}, as one of our most valued patrons, our executive team noticed friction "
                "with your recent experience. We have credited R$ 100 to your account and assigned a dedicated concierge "
                "to ensure your future orders are flawless."
            ),
        ),
        "logistics_friction_recovery": RetentionPlaybook(
            playbook_id="logistics_friction_recovery",
            name="Logistics Friction Recovery & Shipping Waiver",
            description="Automated freight refund, express upgrade, and apology voucher for delivery transit delays.",
            target_criteria="Customers experiencing delivery delays (avg_delivery_delay_days > 2.0 or late orders)",
            intervention_channel="WhatsApp / SMS & Priority Email",
            recommended_action="Instant freight refund, 20% apology discount on next order, and priority carrier dispatch.",
            default_cost_per_customer=22.50,
            estimated_save_rate_min=0.20,
            estimated_save_rate_max=0.35,
            action_template=(
                "We sincerely apologize for the shipping delay on your recent order. We have credited your shipping fees "
                "and unlocked a 20% discount on your next purchase with guaranteed express dispatch."
            ),
        ),
        "sentiment_repair_service": RetentionPlaybook(
            playbook_id="sentiment_repair_service",
            name="Customer Sentiment Repair & Quality Resolution",
            description="Fast-track support ticket and replacement/store credit following poor review feedback.",
            target_criteria="Customers who submitted 1-2 star reviews (avg_review_score <= 2.5 or has_negative_review)",
            intervention_channel="Customer Support Resolution Desk",
            recommended_action="Immediate outbound contact, resolution replacement or store voucher, and merchant review investigation.",
            default_cost_per_customer=28.00,
            estimated_save_rate_min=0.22,
            estimated_save_rate_max=0.38,
            action_template=(
                "Your satisfaction is paramount to us. Our leadership team reviewed your recent feedback and has "
                "initiated a direct resolution ticket with a R$ 50 store credit to make this right."
            ),
        ),
        "automated_reengagement": RetentionPlaybook(
            playbook_id="automated_reengagement",
            name="Automated Win-Back & Promotional Re-engagement",
            description="Algorithmic promotional sequence offering dynamic basket discounts to lapsed buyers.",
            target_criteria="Moderate-to-Low monetary customers drifting into inactivity (P >= 0.70, M <= 3)",
            intervention_channel="Automated Email Sequence & Mobile Push",
            recommended_action="Trigger personalized 15% discount coupon valid for 7 days across top category interests.",
            default_cost_per_customer=8.50,
            estimated_save_rate_min=0.09,
            estimated_save_rate_max=0.18,
            action_template=(
                "We miss you! Here is an exclusive 15% voucher valid for the next 7 days across your favorite categories. "
                "Discover what's new today."
            ),
        ),
        "loyalty_nurture": RetentionPlaybook(
            playbook_id="loyalty_nurture",
            name="VIP Loyalty Nurture & Tier Recognition",
            description="Ongoing relationship reinforcement, early access, and brand advocacy rewards.",
            target_criteria="Champions and Loyal customers with low churn risk (P < 0.30, M >= 4)",
            intervention_channel="In-App Exclusive Experience & VIP Newsletter",
            recommended_action="Early product releases, permanent complimentary shipping, and brand advocate recognition perks.",
            default_cost_per_customer=5.00,
            estimated_save_rate_min=0.06,
            estimated_save_rate_max=0.12,
            action_template=(
                "Thank you for being one of our premier customers. Enjoy early access to our seasonal catalog plus "
                "permanent complimentary express shipping."
            ),
        ),
        "organic_nurture": RetentionPlaybook(
            playbook_id="organic_nurture",
            name="Baseline Operational Communication",
            description="Low-cost transactional communications and periodic newsletters.",
            target_criteria="Standard active buyers with low churn and low spend",
            intervention_channel="Standard Newsletter",
            recommended_action="Automated seasonal catalog updates.",
            default_cost_per_customer=0.50,
            estimated_save_rate_min=0.02,
            estimated_save_rate_max=0.05,
            action_template="Discover this month's top deals and trending marketplace additions.",
        ),
    }

    def get_playbooks(self) -> List[RetentionPlaybook]:
        """Return all cataloged prescriptive retention action playbooks."""
        return list(self.PLAYBOOKS.values())

    def get_playbook(self, playbook_id: str) -> RetentionPlaybook:
        """Fetch a specific playbook by its unique ID."""
        playbook = self.PLAYBOOKS.get(playbook_id)
        if not playbook:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playbook with id '{playbook_id}' not found.",
            )
        return playbook

    def simulate_campaign(
        self, request: CampaignSimulationRequest, db: Optional[Session] = None
    ) -> CampaignSimulationResult:
        """Simulate financial economics, ROI, and break-even save rates for a retention campaign."""
        # Pre-fill defaults from playbook if provided and parameters were not overridden
        cost_per_customer = request.cost_per_customer
        save_rate = request.expected_save_rate

        if request.playbook_id and request.playbook_id in self.PLAYBOOKS:
            pb = self.PLAYBOOKS[request.playbook_id]
            if cost_per_customer <= 0.0:
                cost_per_customer = pb.default_cost_per_customer
            if save_rate <= 0.0:
                save_rate = (pb.estimated_save_rate_min + pb.estimated_save_rate_max) / 2.0

        count = request.target_customer_count
        rar = request.target_revenue_at_risk

        total_cost = round(count * cost_per_customer, 2)
        saved_customers = int(round(count * save_rate))
        gross_saved = round(rar * save_rate, 2)
        net_value = round(gross_saved - total_cost, 2)

        roi = round((net_value / total_cost) * 100, 2) if total_cost > 0 else 0.0
        break_even = round(total_cost / rar, 4) if rar > 0 else 0.0
        efficiency = round(gross_saved / total_cost, 2) if total_cost > 0 else 0.0
        is_profitable = net_value > 0

        # Construct strategic recommendation
        if is_profitable and roi >= 50.0:
            recommendation = (
                f"Highly Profitable: Projected net economic return of R$ {net_value:,.2f} "
                f"with {efficiency:.1f}x capital efficiency (ROI: {roi:.1f}%). "
                f"Break-even retention rate is {break_even:.1%}."
            )
        elif is_profitable:
            recommendation = (
                f"Moderately Profitable: Projected net return of R$ {net_value:,.2f} "
                f"(ROI: {roi:.1f}%). Requires at least {break_even:.1%} save rate to break even."
            )
        else:
            recommendation = (
                f"Unprofitable Intervention: Projected net loss of -R$ {abs(net_value):,.2f}. "
                f"Intervention cost of R$ {cost_per_customer:.2f}/customer exceeds projected risk recovery. "
                f"Requires {break_even:.1%} save rate to break even (current expectation: {save_rate:.1%})."
            )

        return CampaignSimulationResult(
            playbook_id=request.playbook_id,
            target_customer_count=count,
            total_campaign_cost=total_cost,
            target_revenue_at_risk=round(rar, 2),
            projected_customers_saved=saved_customers,
            gross_revenue_saved=gross_saved,
            net_saved_value=net_value,
            roi_percentage=roi,
            break_even_save_rate=break_even,
            capital_efficiency_multiplier=efficiency,
            is_profitable=is_profitable,
            recommendation=recommendation,
        )

    def optimize_budget(
        self, request: BudgetAllocationRequest, db: Optional[Session] = None
    ) -> BudgetAllocationResult:
        """
        Solve optimal capital allocation across candidate retention pools to maximize
        net recovered revenue under a total budget constraint (Knapsack / Marginal Efficiency).
        """
        total_budget = request.total_budget
        pools = request.candidate_pools or self._get_default_pools()

        # Calculate unit economics and efficiency multiplier for each pool
        scored_pools: List[Dict[str, Any]] = []
        for p in pools:
            if p.available_customers <= 0 or p.cost_per_customer <= 0:
                continue

            rar_per_customer = p.total_revenue_at_risk / p.available_customers
            gross_saved_per_customer = rar_per_customer * p.expected_save_rate
            net_gain_per_customer = gross_saved_per_customer - p.cost_per_customer
            marginal_efficiency = (
                gross_saved_per_customer / p.cost_per_customer if p.cost_per_customer > 0 else 0.0
            )

            scored_pools.append(
                {
                    "pool": p,
                    "rar_per_customer": rar_per_customer,
                    "gross_saved_per_customer": gross_saved_per_customer,
                    "net_gain_per_customer": net_gain_per_customer,
                    "marginal_efficiency": marginal_efficiency,
                    "total_pool_cost": p.available_customers * p.cost_per_customer,
                }
            )

        # Sort candidate pools descending by marginal efficiency
        scored_pools.sort(key=lambda x: x["marginal_efficiency"], reverse=True)

        remaining_budget = total_budget
        total_allocated = 0.0
        total_gross_recovered = 0.0
        total_net_value = 0.0
        total_customers_funded = 0
        allocations: List[PoolAllocation] = []

        for item in scored_pools:
            p: CandidatePoolInput = item["pool"]
            cost_per_cust = p.cost_per_customer

            # Skip pools with negative net gain (inefficient spending)
            if item["net_gain_per_customer"] <= 0:
                allocations.append(
                    PoolAllocation(
                        pool_name=p.pool_name,
                        playbook_id=p.playbook_id,
                        customers_targeted=0,
                        max_available_customers=p.available_customers,
                        coverage_ratio=0.0,
                        allocated_spend=0.0,
                        gross_revenue_saved=0.0,
                        net_value=0.0,
                        pool_roi=0.0,
                        marginal_efficiency=round(item["marginal_efficiency"], 2),
                    )
                )
                continue

            # Calculate how many customers we can fund with remaining budget
            max_customers_can_afford = int(remaining_budget // cost_per_cust)
            customers_to_fund = min(p.available_customers, max_customers_can_afford)

            spend = round(customers_to_fund * cost_per_cust, 2)
            gross_saved = round(customers_to_fund * item["gross_saved_per_customer"], 2)
            net_val = round(gross_saved - spend, 2)
            pool_roi = round((net_val / spend) * 100, 2) if spend > 0 else 0.0
            coverage = round(customers_to_fund / p.available_customers, 4)

            remaining_budget = round(remaining_budget - spend, 2)
            total_allocated = round(total_allocated + spend, 2)
            total_gross_recovered = round(total_gross_recovered + gross_saved, 2)
            total_net_value = round(total_net_value + net_val, 2)
            total_customers_funded += customers_to_fund

            allocations.append(
                PoolAllocation(
                    pool_name=p.pool_name,
                    playbook_id=p.playbook_id,
                    customers_targeted=customers_to_fund,
                    max_available_customers=p.available_customers,
                    coverage_ratio=coverage,
                    allocated_spend=spend,
                    gross_revenue_saved=gross_saved,
                    net_value=net_val,
                    pool_roi=pool_roi,
                    marginal_efficiency=round(item["marginal_efficiency"], 2),
                )
            )

        portfolio_roi = (
            round((total_net_value / total_allocated) * 100, 2) if total_allocated > 0 else 0.0
        )
        portfolio_efficiency = (
            round(total_gross_recovered / total_allocated, 2) if total_allocated > 0 else 0.0
        )

        return BudgetAllocationResult(
            total_budget=total_budget,
            allocated_budget=total_allocated,
            remaining_budget=remaining_budget,
            total_customers_targeted=total_customers_funded,
            total_gross_recovered=total_gross_recovered,
            total_net_value=total_net_value,
            portfolio_roi=portfolio_roi,
            portfolio_efficiency=portfolio_efficiency,
            allocations=allocations,
        )

    def _get_default_pools(self) -> List[CandidatePoolInput]:
        """Default customer pools hydrated from established portfolio proportions."""
        return [
            CandidatePoolInput(
                pool_name="VIP Champions & Loyal At-Risk Pool",
                playbook_id="vip_concierge",
                available_customers=2500,
                total_revenue_at_risk=1250000.0,
                cost_per_customer=45.00,
                expected_save_rate=0.35,
            ),
            CandidatePoolInput(
                pool_name="Logistics Delivery Delay Friction Pool",
                playbook_id="logistics_friction_recovery",
                available_customers=5800,
                total_revenue_at_risk=820000.0,
                cost_per_customer=22.50,
                expected_save_rate=0.26,
            ),
            CandidatePoolInput(
                pool_name="Customer Sentiment & Negative Review Pool",
                playbook_id="sentiment_repair_service",
                available_customers=4200,
                total_revenue_at_risk=630000.0,
                cost_per_customer=28.00,
                expected_save_rate=0.30,
            ),
            CandidatePoolInput(
                pool_name="Moderate Value Automated Re-Engagement Pool",
                playbook_id="automated_reengagement",
                available_customers=15000,
                total_revenue_at_risk=750000.0,
                cost_per_customer=8.50,
                expected_save_rate=0.13,
            ),
        ]

    def recommend_for_customer(
        self, customer_unique_id: str, db: Session
    ) -> CustomerPlaybookRecommendation:
        """Determine primary churn root cause and recommend the optimal intervention playbook."""
        query = text(
            """
            SELECT
                c.customer_unique_id,
                c.lifetime_spend,
                c.lifetime_orders,
                c.avg_delivery_delay_days,
                c.has_late_delivery,
                c.avg_review_score,
                c.has_negative_review,
                ch.churn_probability,
                ch.risk_tier,
                ch.revenue_at_risk,
                rfm.segment
            FROM mart.mart_customer_metrics c
            LEFT JOIN ml.churn_predictions ch ON c.customer_unique_id = ch.customer_unique_id
            LEFT JOIN ml.rfm_segments rfm ON c.customer_unique_id = rfm.customer_unique_id
            WHERE c.customer_unique_id = :id
            """
        )
        row = db.execute(query, {"id": customer_unique_id}).mappings().first()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer '{customer_unique_id}' not found.",
            )

        spend = float(row.get("lifetime_spend") or 0.0)
        delay = float(row.get("avg_delivery_delay_days") or 0.0)
        has_late = int(row.get("has_late_delivery") or 0)
        review = float(row.get("avg_review_score") or 4.0)
        has_negative = int(row.get("has_negative_review") or 0)
        churn_prob = float(row.get("churn_probability") or 0.50)
        risk_tier = str(row.get("risk_tier") or "Medium")
        rar = float(row.get("revenue_at_risk") or spend * churn_prob)

        # Diagnose primary churn friction and recommend matching playbook
        if churn_prob >= 0.70 and spend >= 350.0:
            friction = "High-value financial exposure with elevated defection probability"
            playbook = self.PLAYBOOKS["vip_concierge"]
        elif delay > 2.0 or has_late == 1:
            friction = (
                f"Fulfillment friction: carrier transit delay of +{delay:.1f} days past estimate"
            )
            playbook = self.PLAYBOOKS["logistics_friction_recovery"]
        elif review <= 2.5 or has_negative == 1:
            friction = f"Review dissatisfaction: average rating of {review:.1f} stars"
            playbook = self.PLAYBOOKS["sentiment_repair_service"]
        elif churn_prob >= 0.50:
            friction = "Customer purchase lapse: decreasing engagement and order velocity"
            playbook = self.PLAYBOOKS["automated_reengagement"]
        else:
            friction = "Healthy active account profile: low attrition probability"
            playbook = self.PLAYBOOKS["loyalty_nurture"]

        expected_save_rate = (
            playbook.estimated_save_rate_min + playbook.estimated_save_rate_max
        ) / 2.0
        gross_recovery = round(rar * expected_save_rate, 2)
        net_gain = round(gross_recovery - playbook.default_cost_per_customer, 2)

        template_message = playbook.action_template.replace(
            "{customer_name}", f"customer {customer_unique_id[:8]}"
        )

        return CustomerPlaybookRecommendation(
            customer_unique_id=customer_unique_id,
            churn_probability=round(churn_prob, 4),
            risk_tier=risk_tier,
            revenue_at_risk=round(rar, 2),
            primary_friction=friction,
            recommended_playbook=playbook,
            expected_gross_recovery=gross_recovery,
            projected_net_gain=net_gain,
            suggested_message=template_message,
        )
