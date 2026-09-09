"""
tests/test_products.py
======================
Functional and integration tests for product catalog intelligence endpoints.
Validates product listings, category breakdowns, sorting, and product scorecards.
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


def test_list_products_default(client: TestClient) -> None:
    """GET /api/products should return paginated list of catalog products."""
    response = client.get("/api/products")
    assert response.status_code == 200
    data = response.json()

    assert "items" in data
    assert "pagination" in data
    assert len(data["items"]) == 20

    pagination = data["pagination"]
    assert pagination["page"] == 1
    assert pagination["page_size"] == 20
    assert pagination["total_items"] > 30000
    assert pagination["has_next"] is True

    first = data["items"][0]
    assert "product_id" in first
    assert "total_units_sold" in first
    assert "total_revenue" in first
    assert "avg_unit_price" in first


def test_list_products_category_filter(client: TestClient) -> None:
    """GET /api/products?category=health_beauty should filter products by category."""
    response = client.get("/api/products?category=health_beauty&page_size=10")
    assert response.status_code == 200
    data = response.json()

    assert len(data["items"]) == 10
    for p in data["items"]:
        cat_en = (p["category_name_en"] or "").lower()
        cat_pt = (p["category_name_pt"] or "").lower()
        assert "health" in cat_en or "beauty" in cat_en or "beleza" in cat_pt or "saude" in cat_pt


def test_list_products_sorting(client: TestClient) -> None:
    """GET /api/products with sort_by=total_units_sold desc should be ordered."""
    response = client.get("/api/products?sort_by=total_units_sold&sort_order=desc&page_size=10")
    assert response.status_code == 200
    data = response.json()

    units = [p["total_units_sold"] for p in data["items"]]
    assert units == sorted(units, reverse=True)


def test_categories_overview(client: TestClient) -> None:
    """GET /api/products/categories should return aggregate category statistics."""
    response = client.get("/api/products/categories")
    assert response.status_code == 200
    data = response.json()

    assert "total_categories" in data
    assert "categories" in data
    assert data["total_categories"] > 50

    first_cat = data["categories"][0]
    assert "category" in first_cat
    assert "total_products" in first_cat
    assert "total_units_sold" in first_cat
    assert "total_revenue" in first_cat
    assert "avg_price" in first_cat


def test_product_detail_success(client: TestClient) -> None:
    """GET /api/products/{id} should return complete product scorecard."""
    list_res = client.get("/api/products?page_size=1")
    product_id = list_res.json()["items"][0]["product_id"]

    response = client.get(f"/api/products/{product_id}")
    assert response.status_code == 200
    detail = response.json()

    assert detail["product_id"] == product_id
    assert "total_revenue" in detail
    assert "total_units_sold" in detail
    assert "avg_unit_price" in detail


def test_product_detail_not_found(client: TestClient) -> None:
    """GET /api/products/{non_existent_id} should return 404."""
    response = client.get("/api/products/non_existent_product_000000")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
