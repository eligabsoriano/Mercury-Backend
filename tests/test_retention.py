"""
tests/test_retention.py
=======================
Comprehensive automated tests for Phase 9: Prescriptive Retention Economics & Campaign ROI Optimization.
Validates RetentionService, financial simulations, Knapsack budget optimization, customer friction diagnosis,
and REST API endpoints.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.retention import (
    BudgetAllocationRequest,
    CampaignSimulationRequest,
    CandidatePoolInput,
)
from backend.services.retention_service import RetentionService

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — RetentionService
# ─────────────────────────────────────────────────────────────────────────────


class TestRetentionServiceUnit:
    @pytest.fixture
    def service(self) -> RetentionService:
        return RetentionService()

    def test_catalog_retrieval(self, service: RetentionService) -> None:
        playbooks = service.get_playbooks()
        assert len(playbooks) == 6
        ids = {p.playbook_id for p in playbooks}
        assert "vip_concierge" in ids
        assert "logistics_friction_recovery" in ids
        assert "sentiment_repair_service" in ids
        assert "automated_reengagement" in ids
        assert "loyalty_nurture" in ids
        assert "organic_nurture" in ids

    def test_get_playbook_by_id_found(self, service: RetentionService) -> None:
        pb = service.get_playbook("vip_concierge")
        assert pb is not None
        assert pb.playbook_id == "vip_concierge"
        assert pb.default_cost_per_customer == 45.00
        assert pb.intervention_channel == "Direct Phone / Dedicated Account Manager"
        assert pb.estimated_save_rate_min == 0.28
        assert pb.estimated_save_rate_max == 0.45

    def test_get_playbook_by_id_not_found(self, service: RetentionService) -> None:
        with pytest.raises(HTTPException) as exc_info:
            service.get_playbook("non_existent_playbook_999")
        assert exc_info.value.status_code == 404

    def test_simulate_campaign_roi_positive(self, service: RetentionService) -> None:
        req = CampaignSimulationRequest(
            target_customer_count=1000,
            target_revenue_at_risk=200000.0,
            cost_per_customer=35.0,
            expected_save_rate=0.30,
        )
        sim = service.simulate_campaign(req)
        # Total cost: 1000 * 35 = 35,000
        assert sim.total_campaign_cost == 35000.0
        # Expected saved customers: 1000 * 0.30 = 300
        assert sim.projected_customers_saved == 300
        # Gross revenue saved: 200,000 * 0.30 = 60,000
        assert sim.gross_revenue_saved == 60000.0
        # Net value: 60,000 - 35,000 = 25,000
        assert sim.net_saved_value == 25000.0
        # ROI: (25000 / 35000) * 100 = 71.43%
        assert sim.roi_percentage == 71.43
        # Capital efficiency: 60000 / 35000 = 1.71x
        assert sim.capital_efficiency_multiplier == 1.71
        # Break-even save rate: 35000 / 200000 = 0.175
        assert sim.break_even_save_rate == 0.175
        assert sim.is_profitable is True
        assert "highly profitable" in sim.recommendation.lower()

    def test_simulate_campaign_roi_unprofitable(self, service: RetentionService) -> None:
        req = CampaignSimulationRequest(
            target_customer_count=500,
            target_revenue_at_risk=20000.0,
            cost_per_customer=50.0,
            expected_save_rate=0.05,
        )
        sim = service.simulate_campaign(req)
        # Total cost: 500 * 50 = 25,000
        assert sim.total_campaign_cost == 25000.0
        # Gross revenue saved: 20000 * 0.05 = 1,000
        assert sim.gross_revenue_saved == 1000.0
        # Net value: 1,000 - 25,000 = -24,000
        assert sim.net_saved_value == -24000.0
        assert sim.roi_percentage < 0.0
        assert sim.is_profitable is False
        assert "unprofitable" in sim.recommendation.lower()

    def test_optimize_budget_default_pools(self, service: RetentionService) -> None:
        req = BudgetAllocationRequest(total_budget=150000.0)
        res = service.optimize_budget(req)
        assert res.total_budget == 150000.0
        assert res.allocated_budget <= 150000.0
        assert res.remaining_budget >= 0.0
        assert res.total_customers_targeted > 0
        assert res.total_gross_recovered > 0.0
        assert res.total_net_value > 0.0
        assert res.portfolio_roi > 0.0
        assert len(res.allocations) == 4

        # Verify allocations are ranked by marginal efficiency descending
        effs = [a.marginal_efficiency for a in res.allocations]
        assert effs == sorted(effs, reverse=True)

    def test_optimize_budget_insufficient_or_custom_pools(self, service: RetentionService) -> None:
        custom_pools = [
            CandidatePoolInput(
                pool_name="High ROI Pool",
                playbook_id="vip_concierge",
                available_customers=100,
                total_revenue_at_risk=50000.0,
                cost_per_customer=20.0,
                expected_save_rate=0.40,
            ),
            CandidatePoolInput(
                pool_name="Negative ROI Pool",
                playbook_id="logistics_friction_recovery",
                available_customers=50,
                total_revenue_at_risk=500.0,
                cost_per_customer=50.0,
                expected_save_rate=0.01,
            ),
        ]
        # Budget only covers 50 customers of High ROI Pool
        req = BudgetAllocationRequest(total_budget=1000.0, candidate_pools=custom_pools)
        res = service.optimize_budget(req)
        assert res.allocated_budget == 1000.0
        assert res.remaining_budget == 0.0
        assert res.total_customers_targeted == 50

        # Negative ROI pool should be allocated 0 customers
        neg_alloc = next(a for a in res.allocations if a.pool_name == "Negative ROI Pool")
        assert neg_alloc.customers_targeted == 0
        assert neg_alloc.allocated_spend == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# REST API Endpoint Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestRetentionAPI:
    def test_list_playbooks_endpoint(self) -> None:
        response = client.get("/api/retention/playbooks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 6
        first = data[0]
        assert "playbook_id" in first
        assert "name" in first
        assert "target_criteria" in first
        assert "default_cost_per_customer" in first
        assert "estimated_save_rate_min" in first

    def test_get_playbook_detail_endpoint_success(self) -> None:
        response = client.get("/api/retention/playbooks/vip_concierge")
        assert response.status_code == 200
        data = response.json()
        assert data["playbook_id"] == "vip_concierge"
        assert data["default_cost_per_customer"] == 45.0
        assert "recommended_action" in data

    def test_get_playbook_detail_endpoint_not_found(self) -> None:
        response = client.get("/api/retention/playbooks/unknown_playbook_xyz")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_simulate_campaign_roi_endpoint(self) -> None:
        payload = {
            "target_customer_count": 500,
            "target_revenue_at_risk": 75000.0,
            "cost_per_customer": 30.0,
            "expected_save_rate": 0.35,
        }
        response = client.post("/api/retention/campaigns/simulate-roi", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["target_customer_count"] == 500
        assert data["total_campaign_cost"] == 15000.0
        assert data["projected_customers_saved"] == 175
        assert data["gross_revenue_saved"] == 26250.0
        assert data["net_saved_value"] == 11250.0
        assert data["roi_percentage"] == 75.0
        assert data["is_profitable"] is True

    def test_optimize_budget_endpoint(self) -> None:
        payload = {
            "total_budget": 100000.0,
        }
        response = client.post("/api/retention/campaigns/optimize-budget", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["total_budget"] == 100000.0
        assert data["allocated_budget"] <= 100000.0
        assert data["total_customers_targeted"] > 0
        assert len(data["allocations"]) > 0

    def test_recommend_customer_playbook_success(self) -> None:
        # Mock database provides test_cust_001
        response = client.get("/api/retention/recommendations/test_cust_001")
        assert response.status_code == 200
        data = response.json()
        assert data["customer_unique_id"] == "test_cust_001"
        assert "primary_friction" in data
        assert "recommended_playbook" in data
        assert "expected_gross_recovery" in data
        assert "projected_net_gain" in data
        assert "suggested_message" in data

    def test_recommend_customer_playbook_not_found(self) -> None:
        response = client.get("/api/retention/recommendations/missing_customer_999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_root_index_contains_retention_endpoints(self) -> None:
        response = client.get("/")
        assert response.status_code == 200
        endpoints = response.json()["endpoints"]
        assert endpoints["retention_playbooks"] == "/api/retention/playbooks"
        assert endpoints["campaign_simulate_roi"] == "/api/retention/campaigns/simulate-roi"
        assert endpoints["campaign_optimize_budget"] == "/api/retention/campaigns/optimize-budget"
