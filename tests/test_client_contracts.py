"""
tests/test_client_contracts.py
==============================
Tests for Phase 6 Client Integration & Schema Contracts:
- scripts/export_openapi.py CLI and programmatic execution
- openapi.json structure and endpoint coverage
- types/api.ts TypeScript interface definitions
- docs/powerbi_setup.md DirectQuery and DAX metric documentation
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.export_openapi import export_openapi, generate_openapi_schema

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_export_openapi_programmatic() -> None:
    """Verifies that generate_openapi_schema returns a valid OpenAPI 3.x document."""
    schema = generate_openapi_schema()
    assert isinstance(schema, dict)
    assert schema.get("openapi", "").startswith("3.")
    assert "Mercury" in schema.get("info", {}).get("title", "")
    assert "paths" in schema
    assert len(schema["paths"]) >= 15


def test_export_openapi_file_generation(tmp_path: Path) -> None:
    """Verifies that export_openapi writes valid JSON to the target path."""
    dest = tmp_path / "test_openapi.json"
    exported = export_openapi(dest)
    assert exported.is_file()

    with open(exported, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data.get("openapi", "").startswith("3.")
    assert "/api/customers" in data.get("paths", {})
    assert "/api/auth/token" in data.get("paths", {})


def test_static_openapi_json_exists_and_valid() -> None:
    """Verifies that the static openapi.json exists at root and covers all core routes."""
    openapi_file = PROJECT_ROOT / "openapi.json"
    assert openapi_file.is_file(), "openapi.json must exist at project root"

    with open(openapi_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    paths = data.get("paths", {})
    expected_endpoints = [
        "/",
        "/health",
        "/api/health",
        "/api/health/pipeline",
        "/api/auth/token",
        "/api/auth/me",
        "/api/analytics/overview",
        "/api/analytics/segments",
        "/api/analytics/revenue-at-risk",
        "/api/analytics/revenue",
        "/api/analytics/retention",
        "/api/customers",
        "/api/customers/at-risk",
        "/api/customers/export",
        "/api/products",
        "/api/products/categories",
        "/api/sellers",
        "/api/predictions/churn",
        "/api/predictions/churn/simulate",
        "/api/predictions/model/info",
        "/api/retention/playbooks",
        "/api/retention/campaigns/simulate-roi",
        "/api/retention/campaigns/optimize-budget",
        "/api/retention/recommendations/{customer_unique_id}",
        "/api/marketing/overview",
        "/api/marketing/channels",
        "/api/marketing/velocity",
        "/api/marketing/segments",
        "/api/marketing/leads",
    ]
    for endpoint in expected_endpoints:
        assert endpoint in paths, f"Expected endpoint '{endpoint}' in openapi.json"


def test_typescript_types_exist_and_complete() -> None:
    """Verifies that types/api.ts contains exported TypeScript interfaces for paths and schemas."""
    ts_file = PROJECT_ROOT / "types" / "api.ts"
    assert ts_file.is_file(), "types/api.ts must exist"

    content = ts_file.read_text(encoding="utf-8")
    assert "export interface paths" in content
    assert "export interface operations" in content
    assert "export interface components" in content

    # Key schema models
    expected_schemas = [
        "PortfolioOverview",
        "CustomerDetail",
        "CustomerSummary",
        "CustomerListResponse",
        "ProductSummary",
        "SellerSummary",
        "TokenResponse",
        "ChurnPredictionResult",
        "CounterfactualSimulationResponse",
        "RetentionPlaybook",
        "CampaignSimulationResult",
        "BudgetAllocationResult",
        "CustomerPlaybookRecommendation",
        "MarketingFunnelOverview",
        "ChannelAttributionResponse",
        "SalesVelocityMetrics",
        "SegmentPerformanceResponse",
        "MarketingLeadsListResponse",
        "PipelineHealthResponse",
    ]
    for schema_name in expected_schemas:
        assert schema_name in content, f"Expected schema '{schema_name}' in types/api.ts"


def test_powerbi_documentation_exists_and_detailed() -> None:
    """Verifies that docs/powerbi_setup.md details DirectQuery, model relationships, and DAX."""
    pbi_file = PROJECT_ROOT / "docs" / "powerbi_setup.md"
    assert pbi_file.is_file(), "docs/powerbi_setup.md must exist"

    content = pbi_file.read_text(encoding="utf-8")

    # Connection & Mode
    assert "DirectQuery" in content
    assert "Neon" in content

    # Tables & Star Schema
    assert "fact_orders" in content
    assert "dim_customers" in content
    assert "mart_customer_metrics" in content
    assert "churn_predictions" in content

    # Core DAX measures
    assert "Total GMV" in content
    assert "Total Orders" in content
    assert "Average Order Value" in content
    assert "Portfolio Revenue at Risk" in content
    assert "Repeat Purchase Rate" in content


def test_package_json_codegen_scripts() -> None:
    """Verifies that package.json exists and configures codegen scripts."""
    pkg_file = PROJECT_ROOT / "package.json"
    assert pkg_file.is_file(), "package.json must exist"

    with open(pkg_file, "r", encoding="utf-8") as f:
        pkg = json.load(f)

    scripts = pkg.get("scripts", {})
    assert "codegen" in scripts
    assert "export:openapi" in scripts
    assert "generate:types" in scripts
