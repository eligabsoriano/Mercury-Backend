"""
tests/test_sellers.py
=====================
Functional and integration tests for marketplace seller intelligence endpoints.
Validates pagination, state filtering, revenue sorting, and seller 360 profiles.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Provides a synchronous FastAPI TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client


def test_list_sellers_default(client: TestClient) -> None:
    """GET /api/sellers should return paginated list of marketplace sellers."""
    response = client.get("/api/sellers")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "pagination" in data
    assert len(data["items"]) == 20

    pagination = data["pagination"]
    assert pagination["page"] == 1
    assert pagination["page_size"] == 20
    assert pagination["total_items"] > 0
    assert pagination["has_next"] is True

    first = data["items"][0]
    assert "seller_id" in first
    assert "city" in first
    assert "state" in first
    assert "total_orders_fulfilled" in first
    assert "total_revenue" in first
    assert "avg_delivery_delay_days" in first
    assert "late_delivery_rate" in first
    assert "avg_review_score" in first


def test_list_sellers_state_filter(client: TestClient) -> None:
    """GET /api/sellers?state=SP should filter sellers to Sao Paulo state."""
    response = client.get("/api/sellers?state=SP&page_size=10")
    assert response.status_code == 200
    data = response.json()

    assert len(data["items"]) == 10
    for seller in data["items"]:
        assert seller["state"] == "SP"


def test_list_sellers_sorting(client: TestClient) -> None:
    """GET /api/sellers with sort_by=total_orders_fulfilled desc should be sorted."""
    response = client.get(
        "/api/sellers?sort_by=total_orders_fulfilled&sort_order=desc&page_size=10"
    )
    assert response.status_code == 200
    data = response.json()

    orders_list = [s["total_orders_fulfilled"] for s in data["items"]]
    assert orders_list == sorted(orders_list, reverse=True)


def test_list_sellers_search(client: TestClient) -> None:
    """GET /api/sellers?search=curitiba should match sellers from Curitiba."""
    response = client.get("/api/sellers?search=curitiba&page_size=10")
    assert response.status_code == 200
    data = response.json()

    assert len(data["items"]) > 0
    for s in data["items"]:
        assert "curitiba" in s["city"].lower() or "curitiba" in s["seller_id"].lower()


def test_seller_detail_success(client: TestClient) -> None:
    """GET /api/sellers/{id} should return comprehensive seller profile."""
    # First get a valid seller_id from list
    list_res = client.get("/api/sellers?page_size=1")
    seller_id = list_res.json()["items"][0]["seller_id"]

    response = client.get(f"/api/sellers/{seller_id}")
    assert response.status_code == 200
    detail = response.json()

    assert detail["seller_id"] == seller_id
    assert "top_categories" in detail
    assert "total_revenue" in detail
    assert "late_delivery_rate" in detail
    assert "positive_reviews_rate" in detail


def test_seller_detail_not_found(client: TestClient) -> None:
    """GET /api/sellers/{non_existent_id} should return 404."""
    response = client.get("/api/sellers/non_existent_seller_id_000000")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
