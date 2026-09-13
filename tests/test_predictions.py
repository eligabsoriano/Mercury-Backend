"""
tests/test_predictions.py
==========================
Comprehensive automated tests for Phase 8: Real-Time ML Inference & Counterfactual Simulation.
Validates PredictionService, feature preparation, counterfactual deltas, and REST API endpoints.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.prediction_service import PredictionService

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — PredictionService
# ─────────────────────────────────────────────────────────────────────────────


class TestPredictionService:
    def test_service_singleton(self):
        s1 = PredictionService.get_instance()
        s2 = PredictionService.get_instance()
        assert s1 is s2
        assert s1.pipeline is not None
        assert "model_name" in s1.metadata

    def test_predict_standard_features(self):
        service = PredictionService.get_instance()
        result = service.predict(
            {
                "lifetime_spend": 450.0,
                "lifetime_orders": 3,
                "avg_delivery_delay_days": -2.0,
                "avg_review_score": 4.8,
                "segment": "Loyal Customers",
            }
        )
        assert 0.0 <= result.churn_probability <= 1.0
        assert result.risk_tier in ["High", "Medium", "Low"]
        assert result.monetary_value == 450.0
        assert result.revenue_at_risk >= 0.0
        assert "Priority" in result.retention_priority or "Medium" in result.retention_priority
        assert len(result.top_feature_contributions) > 0

    def test_predict_high_risk_profile(self):
        service = PredictionService.get_instance()
        result = service.predict(
            {
                "lifetime_spend": 600.0,
                "lifetime_orders": 1,
                "avg_delivery_delay_days": 8.5,
                "avg_review_score": 1.0,
                "has_negative_review": 1,
                "negative_reviews_count": 1,
                "late_orders_count": 1,
                "has_late_delivery": 1,
                "freight_ratio": 0.35,
                "segment": "At Risk",
            }
        )
        # High delay + 1 star review + single order should predict high risk
        assert result.churn_probability >= 0.70
        assert result.risk_tier == "High"
        assert result.retention_priority == "Priority 1: Immediate VIP Retention"

    def test_counterfactual_simulation_interventions_reduce_risk(self):
        service = PredictionService.get_instance()
        base = {
            "lifetime_spend": 500.0,
            "lifetime_orders": 2,
            "avg_delivery_delay_days": 7.0,
            "avg_review_score": 2.0,
            "segment": "Potential Loyalists",
        }
        adjustments = {
            "avg_delivery_delay_days": 0.0,
            "avg_review_score": 5.0,
        }
        sim = service.simulate_counterfactual(base_features=base, adjustments=adjustments)

        assert sim.delta_churn_probability < 0.0, "Expected churn probability to decrease"
        assert sim.delta_revenue_at_risk < 0.0, "Expected revenue at risk to decrease (savings)"
        assert sim.simulated.churn_probability < sim.baseline.churn_probability
        assert "reduce churn probability" in sim.impact_summary.lower()

    def test_counterfactual_simulation_degradation_increases_risk(self):
        service = PredictionService.get_instance()
        base = {
            "lifetime_spend": 300.0,
            "lifetime_orders": 2,
            "avg_delivery_delay_days": -4.0,
            "avg_review_score": 5.0,
            "segment": "Loyal Customers",
        }
        adjustments = {
            "avg_delivery_delay_days": 10.0,
            "avg_review_score": 1.0,
        }
        sim = service.simulate_counterfactual(base_features=base, adjustments=adjustments)

        assert sim.delta_churn_probability > 0.0, "Expected churn probability to increase"
        assert sim.delta_revenue_at_risk > 0.0, "Expected revenue at risk to increase"
        assert "increase churn probability" in sim.impact_summary.lower()

    def test_model_info_metadata(self):
        service = PredictionService.get_instance()
        info = service.get_model_info()
        assert info.model_name
        assert info.window_days == 90
        assert len(info.numeric_features) == 25
        assert len(info.categorical_features) == 1
        assert "roc_auc" in info.eval_metrics
        assert info.eval_metrics["roc_auc"] > 0.5


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoint Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPredictionAPI:
    def test_post_predict_churn_success(self):
        payload = {
            "lifetime_spend": 350.0,
            "lifetime_orders": 2,
            "avg_delivery_delay_days": 4.0,
            "avg_review_score": 2.5,
            "segment": "At Risk",
        }
        response = client.post("/api/predictions/churn", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "churn_probability" in data
        assert "risk_tier" in data
        assert data["monetary_value"] == 350.0
        assert "revenue_at_risk" in data
        assert "retention_priority" in data
        assert isinstance(data["top_feature_contributions"], list)

    def test_post_predict_churn_empty_features_uses_defaults(self):
        response = client.post("/api/predictions/churn", json={})
        assert response.status_code == 200
        data = response.json()
        assert 0.0 <= data["churn_probability"] <= 1.0
        assert data["risk_tier"] in ["High", "Medium", "Low"]

    def test_post_simulate_counterfactual_inline(self):
        payload = {
            "base_features": {
                "lifetime_spend": 400.0,
                "lifetime_orders": 2,
                "avg_delivery_delay_days": 6.0,
                "avg_review_score": 2.0,
                "segment": "Potential Loyalists",
            },
            "adjustments": {
                "avg_delivery_delay_days": 0.0,
                "avg_review_score": 5.0,
            },
        }
        response = client.post("/api/predictions/churn/simulate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "baseline" in data
        assert "simulated" in data
        assert data["delta_churn_probability"] < 0.0
        assert data["delta_revenue_at_risk"] < 0.0
        assert "risk_tier_transition" in data
        assert "impact_summary" in data

    def test_post_simulate_customer_by_path_param_success(self):
        list_res = client.get("/api/customers?page_size=1")
        customer_id = list_res.json()["items"][0]["customer_unique_id"]
        payload = {
            "avg_delivery_delay_days": 0.0,
            "avg_review_score": 5.0,
        }
        response = client.post(
            f"/api/predictions/churn/simulate/{customer_id}",
            json=payload,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["customer_unique_id"] == customer_id
        assert "baseline" in data
        assert "simulated" in data
        assert "delta_churn_probability" in data

    def test_post_simulate_customer_not_found(self):
        payload = {
            "avg_delivery_delay_days": 0.0,
        }
        response = client.post(
            "/api/predictions/churn/simulate/missing_cust_xyz999",
            json=payload,
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_model_info_success(self):
        response = client.get("/api/predictions/model/info")
        assert response.status_code == 200
        data = response.json()
        assert data["model_name"]
        assert data["window_days"] == 90
        assert len(data["numeric_features"]) == 25
        assert len(data["categorical_features"]) == 1
        assert "eval_metrics" in data

    def test_root_index_contains_prediction_endpoints(self):
        response = client.get("/")
        assert response.status_code == 200
        endpoints = response.json()["endpoints"]
        assert endpoints["predict_churn"] == "/api/predictions/churn"
        assert endpoints["simulate_churn"] == "/api/predictions/churn/simulate"
        assert endpoints["model_info"] == "/api/predictions/model/info"
