"""
tests/test_api.py
=================
Integration and functional tests for the Mercury FastAPI application.
Validates HTTP endpoints, response contracts, Pydantic schemas, pagination,
error handling, filtering, and database query executions.
"""

from __future__ import annotations

import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Provides a synchronous FastAPI TestClient instance for route tests."""
    with TestClient(app) as test_client:
        yield test_client


# ===========================================================================
# 1. Health & Documentation Endpoints
# ===========================================================================

def test_root_index(client: TestClient) -> None:
    """GET / should return 200 with service metadata and documentation links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "documentation" in data
    assert data["documentation"]["swagger_ui"] == "/docs"
    assert "endpoints" in data


def test_health_check(client: TestClient) -> None:
    """GET /health and /api/health should return system status and DB latency."""
    for path in ["/health", "/api/health"]:
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")
        assert "database" in data
        assert "connected" in data["database"]
        assert data["database"]["connected"] is True


def test_openapi_spec(client: TestClient) -> None:
    """GET /openapi.json should return valid OpenAPI 3.x specification."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "openapi" in spec
    assert spec["info"]["title"] == "Mercury Customer Intelligence API"
    assert "/api/analytics/overview" in spec["paths"]
    assert "/api/customers" in spec["paths"]


# ===========================================================================
# 2. Portfolio Analytics Endpoints
# ===========================================================================

def test_analytics_overview(client: TestClient) -> None:
    """GET /api/analytics/overview should return macro-level portfolio KPIs."""
    response = client.get("/api/analytics/overview")
    assert response.status_code == 200
    data = response.json()

    assert data["total_customers"] == 93358
    assert data["total_orders"] >= 90000
    assert data["total_revenue"] > 10000000.0  # R$ 15.42M
    assert data["avg_order_value"] > 0.0
    assert 0.0 <= data["repeat_buyer_rate"] <= 100.0
    assert data["portfolio_revenue_at_risk"] > 0.0
    assert data["portfolio_risk_percentage"] > 0.0
    assert 0.0 <= data["avg_churn_probability"] <= 1.0
    assert data["high_risk_customers_count"] > 0
    assert data["vip_retention_revenue_at_risk"] > 0.0


def test_analytics_segments(client: TestClient) -> None:
    """GET /api/analytics/segments should return RFM segment distribution."""
    response = client.get("/api/analytics/segments")
    assert response.status_code == 200
    data = response.json()

    assert data["total_customers"] == 93358
    segments = data["segments"]
    assert len(segments) > 0

    segment_names = [s["segment"] for s in segments]
    assert "Champions" in segment_names
    assert "Lost / Inactive" in segment_names

    # Check that percentages sum close to 100%
    total_pct = sum(s["percentage"] for s in segments)
    assert 99.0 <= total_pct <= 101.0


def test_analytics_rfm_alias(client: TestClient) -> None:
    """GET /api/analytics/rfm should return the same schema as /segments."""
    response = client.get("/api/analytics/rfm")
    assert response.status_code == 200
    data = response.json()
    assert data["total_customers"] == 93358
    assert len(data["segments"]) > 0


def test_analytics_revenue_at_risk(client: TestClient) -> None:
    """GET /api/analytics/revenue-at-risk should return financial risk breakdown."""
    response = client.get("/api/analytics/revenue-at-risk?include_preview=true")
    assert response.status_code == 200
    data = response.json()

    assert data["total_revenue_at_risk"] > 10000000.0
    assert data["total_historical_spend"] > 15000000.0
    assert 50.0 <= data["portfolio_risk_percentage"] <= 90.0

    # Risk tiers
    tiers = {t["risk_tier"]: t for t in data["by_risk_tier"]}
    assert "High" in tiers
    assert "Medium" in tiers
    assert "Low" in tiers
    assert tiers["High"]["customer_count"] > 0

    # Retention priorities
    priorities = {p["retention_priority"]: p for p in data["by_retention_priority"]}
    assert "Priority 1: Immediate VIP Retention" in priorities

    # Preview
    assert data["top_at_risk_preview"] is not None
    assert len(data["top_at_risk_preview"]) == 5


def test_analytics_caching_and_bypass(client: TestClient) -> None:
    """Verify in-memory TTL caching and bypass_cache query parameter across analytics endpoints."""
    # 1. Clear cache to establish clean baseline
    clear_res = client.post("/api/analytics/cache/clear")
    assert clear_res.status_code == 200
    assert clear_res.json()["status"] == "cleared"

    # 2. First call to /overview: cache miss
    res1 = client.get("/api/analytics/overview")
    assert res1.status_code == 200

    # 3. Second call to /overview: cache hit
    res2 = client.get("/api/analytics/overview")
    assert res2.status_code == 200
    assert res1.json() == res2.json()

    # 4. Third call with bypass_cache=true: forces live re-query
    res3 = client.get("/api/analytics/overview?bypass_cache=true")
    assert res3.status_code == 200
    assert res3.json()["total_customers"] == 93358

    # 5. Inspect cache telemetry
    stats_res = client.get("/api/analytics/cache/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["hits"] >= 1
    assert stats["bypasses"] >= 1
    assert stats["active_items"] >= 1

    # 6. Verify bypass_cache on segments and revenue-at-risk
    seg_res = client.get("/api/analytics/segments?bypass_cache=true")
    assert seg_res.status_code == 200
    rar_res = client.get("/api/analytics/revenue-at-risk?bypass_cache=true")
    assert rar_res.status_code == 200


# ===========================================================================
# 3. Customer Listing & Filtering Endpoints
# ===========================================================================

def test_list_customers_default_pagination(client: TestClient) -> None:
    """GET /api/customers should return first page with default page_size=20."""
    response = client.get("/api/customers")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "pagination" in data
    assert len(data["items"]) == 20

    pagination = data["pagination"]
    assert pagination["page"] == 1
    assert pagination["page_size"] == 20
    assert pagination["total_items"] == 93358
    assert pagination["total_pages"] == 4668
    assert pagination["has_next"] is True
    assert pagination["has_prev"] is False

    # Inspect first customer summary fields
    first = data["items"][0]
    assert "customer_unique_id" in first
    assert "lifetime_spend" in first
    assert "lifetime_orders" in first
    assert "segment" in first
    assert "churn_probability" in first
    assert "risk_tier" in first


def test_list_customers_custom_pagination(client: TestClient) -> None:
    """GET /api/customers?page=2&page_size=10 should return 10 items for page 2."""
    response = client.get("/api/customers?page=2&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    assert data["pagination"]["page"] == 2
    assert data["pagination"]["page_size"] == 10
    assert data["pagination"]["has_prev"] is True


def test_list_customers_filter_risk_tier(client: TestClient) -> None:
    """GET /api/customers?risk_tier=High should only return High risk customers."""
    response = client.get("/api/customers?risk_tier=High&page_size=15")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 15
    for item in data["items"]:
        assert item["risk_tier"] == "High"
        assert item["churn_probability"] >= 0.70


def test_list_customers_filter_segment(client: TestClient) -> None:
    """GET /api/customers?segment=Champions should only return Champions."""
    response = client.get("/api/customers?segment=Champions&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    for item in data["items"]:
        assert item["segment"] == "Champions"


def test_list_customers_filter_state(client: TestClient) -> None:
    """GET /api/customers?state=SP should only return customers located in SP."""
    response = client.get("/api/customers?state=SP&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10
    for item in data["items"]:
        assert item["state"] == "SP"


def test_list_customers_filter_spend_range(client: TestClient) -> None:
    """GET /api/customers?min_spend=500&max_spend=1000 should filter spend."""
    response = client.get("/api/customers?min_spend=500&max_spend=1000&page_size=10")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert 500.0 <= item["lifetime_spend"] <= 1000.0


def test_list_customers_sorting(client: TestClient) -> None:
    """GET /api/customers?sort_by=recency_days&sort_order=asc should sort ascending."""
    response = client.get("/api/customers?sort_by=recency_days&sort_order=asc&page_size=10")
    assert response.status_code == 200
    data = response.json()
    recencies = [item["recency_days"] for item in data["items"] if item["recency_days"] is not None]
    assert recencies == sorted(recencies)


def test_list_customers_search(client: TestClient) -> None:
    """GET /api/customers?search=000 should filter matching prefix/substring."""
    response = client.get("/api/customers?search=000&page_size=5")
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert "000" in item["customer_unique_id"]


# ===========================================================================
# 4. At-Risk Queue & Convenience Endpoints
# ===========================================================================

def test_customers_at_risk_queue(client: TestClient) -> None:
    """GET /api/customers/at-risk should return queue ordered by revenue_at_risk DESC."""
    response = client.get("/api/customers/at-risk?page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 10

    # Verify descending ordering by revenue_at_risk
    rars = [item["revenue_at_risk"] for item in data["items"]]
    assert rars == sorted(rars, reverse=True)


def test_customers_segments_convenience_alias(client: TestClient) -> None:
    """GET /api/customers/segments should return segments overview."""
    response = client.get("/api/customers/segments")
    assert response.status_code == 200
    data = response.json()
    assert data["total_customers"] == 93358


# ===========================================================================
# 5. Customer 360 Detail, RFM & Churn Single-Customer Endpoints
# ===========================================================================

def test_customer_detail_success_and_404(client: TestClient) -> None:
    """GET /api/customers/{id} should return 360 detail for valid customer, 404 for missing."""
    # First fetch a known valid ID from list
    list_res = client.get("/api/customers?page_size=1")
    customer_id = list_res.json()["items"][0]["customer_unique_id"]

    # 1. Fetch valid customer detail
    detail_res = client.get(f"/api/customers/{customer_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()

    assert detail["customer_unique_id"] == customer_id
    assert "basket" in detail
    assert "fulfillment" in detail
    assert "reviews" in detail
    assert "rfm" in detail
    assert "churn" in detail
    assert detail["basket"]["lifetime_items"] >= 1

    # 2. Fetch non-existent customer
    missing_res = client.get("/api/customers/nonexistent_customer_id_99999")
    assert missing_res.status_code == 404
    assert "not found" in missing_res.json()["detail"].lower()


def test_customer_rfm_scorecard_and_404(client: TestClient) -> None:
    """GET /api/customers/{id}/rfm should return RFM scorecard for valid ID, 404 for missing."""
    list_res = client.get("/api/customers?page_size=1")
    customer_id = list_res.json()["items"][0]["customer_unique_id"]

    # Valid customer
    rfm_res = client.get(f"/api/customers/{customer_id}/rfm")
    assert rfm_res.status_code == 200
    rfm = rfm_res.json()
    assert rfm["customer_unique_id"] == customer_id
    assert 1 <= rfm["r_score"] <= 5
    assert 1 <= rfm["f_score"] <= 5
    assert 1 <= rfm["m_score"] <= 5
    assert rfm["segment"] != ""

    # Non-existent customer
    missing_res = client.get("/api/customers/missing_rfm_id_000/rfm")
    assert missing_res.status_code == 404


def test_customer_churn_prediction_and_404(client: TestClient) -> None:
    """GET /api/customers/{id}/churn should return churn prediction for valid ID, 404 for missing."""
    list_res = client.get("/api/customers?page_size=1")
    customer_id = list_res.json()["items"][0]["customer_unique_id"]

    # Valid customer
    churn_res = client.get(f"/api/customers/{customer_id}/churn")
    assert churn_res.status_code == 200
    churn = churn_res.json()
    assert churn["customer_unique_id"] == customer_id
    assert 0.0 <= churn["churn_probability"] <= 1.0
    assert churn["risk_tier"] in ("High", "Medium", "Low")
    assert churn["revenue_at_risk"] >= 0.0
    assert churn["retention_priority"] != ""

    # Non-existent customer
    missing_res = client.get("/api/customers/missing_churn_id_000/churn")
    assert missing_res.status_code == 404


# ===========================================================================
# 6. Parameter Validation & Edge Cases
# ===========================================================================

def test_pagination_validation_errors(client: TestClient) -> None:
    """Query parameter validation should return 422 for illegal page or page_size."""
    # Page must be >= 1
    res_page_zero = client.get("/api/customers?page=0")
    assert res_page_zero.status_code == 422

    # Page size must be <= 100
    res_size_too_large = client.get("/api/customers?page_size=101")
    assert res_size_too_large.status_code == 422

    # Negative spend
    res_neg_spend = client.get("/api/customers?min_spend=-10")
    assert res_neg_spend.status_code == 422
