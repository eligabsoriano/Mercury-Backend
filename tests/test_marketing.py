"""
tests/test_marketing.py
=======================
Comprehensive automated tests for Phase 10: Two-Sided Marketplace Marketing Funnel,
Seller Acquisition Velocity, and Origin Channel Attribution.
Validates MarketingService and REST API endpoints.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.marketing_service import MarketingService

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — MarketingService
# ─────────────────────────────────────────────────────────────────────────────


class TestMarketingServiceUnit:
    def test_get_funnel_overview(self) -> None:
        # Uses session provided by conftest
        from tests.conftest import MockSession

        session = MockSession()
        overview = MarketingService.get_funnel_overview(session, bypass_cache=True)
        assert overview.total_leads == 8000
        assert overview.total_closed_deals == 842
        assert overview.overall_conversion_rate == 10.53
        assert overview.avg_days_to_close == 48.7
        assert overview.total_declared_monthly_revenue == 6250000.0
        assert overview.total_actual_marketplace_revenue == 1280000.0
        assert overview.active_marketplace_sellers_count == 380
        assert overview.seller_activation_rate == 45.13

    def test_get_channel_attribution(self) -> None:
        from tests.conftest import MockSession

        session = MockSession()
        res = MarketingService.get_channel_attribution(session, bypass_cache=True)
        assert res.total_channels >= 6
        assert len(res.channels) == res.total_channels
        first = res.channels[0]
        assert first.origin
        assert first.leads_count > 0
        assert first.closed_deals_count > 0
        assert first.conversion_rate > 0.0
        assert first.share_of_leads_percent > 0.0

    def test_get_sales_velocity(self) -> None:
        from tests.conftest import MockSession

        session = MockSession()
        vel = MarketingService.get_sales_velocity(session, bypass_cache=True)
        assert vel.overall_avg_days_to_close == 48.7
        assert vel.fastest_segment == "reseller"
        assert vel.slowest_segment == "health_beauty"
        assert len(vel.velocity_by_segment) > 0
        assert len(vel.velocity_by_lead_type) > 0
        seg = vel.velocity_by_segment[0]
        assert seg.business_segment == "reseller"
        assert seg.avg_days_to_close == 32.4
        assert seg.min_days_to_close == 2
        assert seg.max_days_to_close == 120

    def test_get_segment_performance(self) -> None:
        from tests.conftest import MockSession

        session = MockSession()
        res = MarketingService.get_segment_performance(session, bypass_cache=True)
        assert res.total_segments >= 3
        assert len(res.segments) == res.total_segments
        top_seg = res.segments[0]
        assert top_seg.business_segment == "reseller"
        assert top_seg.closed_deals_count == 180
        assert top_seg.total_actual_marketplace_revenue == 450000.0
        assert top_seg.active_sellers_count == 95

    def test_list_leads_default(self) -> None:
        from tests.conftest import MockSession

        session = MockSession()
        res = MarketingService.list_leads(session, page=1, page_size=20)
        assert len(res.items) == 20
        assert res.pagination.page == 1
        assert res.pagination.page_size == 20
        assert res.pagination.total_items == 8000
        assert res.pagination.total_pages == 400
        assert res.pagination.has_next is True
        first = res.items[0]
        assert first.mql_id
        assert first.origin
        assert isinstance(first.is_won, bool)


# ─────────────────────────────────────────────────────────────────────────────
# REST API Endpoint Integration Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestMarketingAPI:
    def test_get_funnel_overview_endpoint(self) -> None:
        response = client.get("/api/marketing/overview")
        assert response.status_code == 200
        data = response.json()
        assert data["total_leads"] == 8000
        assert data["total_closed_deals"] == 842
        assert data["overall_conversion_rate"] == 10.53
        assert data["avg_days_to_close"] == 48.7
        assert "total_declared_monthly_revenue" in data
        assert "total_actual_marketplace_revenue" in data
        assert "active_marketplace_sellers_count" in data
        assert "seller_activation_rate" in data

    def test_get_channel_attribution_endpoint(self) -> None:
        response = client.get("/api/marketing/channels")
        assert response.status_code == 200
        data = response.json()
        assert "channels" in data
        assert "total_channels" in data
        assert data["total_channels"] >= 6
        ch = data["channels"][0]
        assert "origin" in ch
        assert "leads_count" in ch
        assert "closed_deals_count" in ch
        assert "conversion_rate" in ch
        assert "share_of_leads_percent" in ch

    def test_get_sales_velocity_endpoint(self) -> None:
        response = client.get("/api/marketing/velocity")
        assert response.status_code == 200
        data = response.json()
        assert data["overall_avg_days_to_close"] == 48.7
        assert "fastest_segment" in data
        assert "slowest_segment" in data
        assert isinstance(data["velocity_by_segment"], list)
        assert isinstance(data["velocity_by_lead_type"], list)

    def test_get_segment_performance_endpoint(self) -> None:
        response = client.get("/api/marketing/segments")
        assert response.status_code == 200
        data = response.json()
        assert "segments" in data
        assert "total_segments" in data
        assert data["total_segments"] >= 3
        seg = data["segments"][0]
        assert "business_segment" in seg
        assert "closed_deals_count" in seg
        assert "total_actual_marketplace_revenue" in seg
        assert "active_sellers_count" in seg

    def test_list_marketing_leads_default(self) -> None:
        response = client.get("/api/marketing/leads")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert len(data["items"]) == 20
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 20
        assert data["pagination"]["total_items"] == 8000

    def test_list_marketing_leads_filtered(self) -> None:
        response = client.get("/api/marketing/leads?origin=organic_search&page=1&page_size=10")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 10
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["page_size"] == 10
        assert data["pagination"]["total_items"] in (15, 2296)
        assert data["pagination"]["total_pages"] in (2, 230)

    def test_root_index_contains_marketing_endpoints(self) -> None:
        response = client.get("/")
        assert response.status_code == 200
        endpoints = response.json()["endpoints"]
        assert endpoints["marketing_overview"] == "/api/marketing/overview"
        assert endpoints["marketing_channels"] == "/api/marketing/channels"
        assert endpoints["marketing_velocity"] == "/api/marketing/velocity"
        assert endpoints["marketing_segments"] == "/api/marketing/segments"
        assert endpoints["marketing_leads"] == "/api/marketing/leads"
