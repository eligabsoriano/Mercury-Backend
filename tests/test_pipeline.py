"""
tests/test_pipeline.py
======================
Unit and functional tests for the Mercury Unified Pipeline Orchestrator
and the GET /api/health/pipeline observability endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.pipeline_service import pipeline_service
from scripts.run_pipeline import VALID_STEPS, PipelineOrchestrator


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Provides a synchronous FastAPI TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client


# ===========================================================================
# 1. Pipeline Orchestrator CLI Runner Tests
# ===========================================================================


class TestPipelineOrchestrator:
    """Validates the execution, timing, arguments, and dry-run modes of scripts/run_pipeline.py."""

    def test_orchestrator_initialization_defaults(self, tmp_path: Path) -> None:
        status_file = tmp_path / "status.json"
        orch = PipelineOrchestrator(
            steps=VALID_STEPS,
            dry_run=True,
            status_file=status_file,
        )
        assert orch.steps == VALID_STEPS
        assert orch.dry_run is True
        assert orch.window == 90
        assert orch.truncate is False
        assert orch.skip_tests is False

    def test_orchestrator_invalid_step_raises(self, tmp_path: Path) -> None:
        status_file = tmp_path / "status.json"
        with pytest.raises(ValueError, match="Unknown pipeline step"):
            PipelineOrchestrator(
                steps=["db_check", "non_existent_step"],
                dry_run=True,
                status_file=status_file,
            )

    def test_orchestrator_dry_run_execution(self, tmp_path: Path) -> None:
        status_file = tmp_path / "test_status.json"
        orch = PipelineOrchestrator(
            steps=VALID_STEPS,
            dry_run=True,
            status_file=status_file,
        )
        record = orch.run()

        assert record["status"] == "success"
        assert record["dry_run"] is True
        assert len(record["steps_executed"]) == 6
        assert "db_check" in record["step_results"]
        assert record["step_results"]["db_check"]["success"] is True
        assert record["step_results"]["codegen"]["success"] is True

        # Ensure status JSON file was written correctly
        assert status_file.exists()
        with open(status_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
            assert saved["run_id"] == record["run_id"]
            assert saved["status"] == "success"

    def test_orchestrator_selective_steps(self, tmp_path: Path) -> None:
        status_file = tmp_path / "selective.json"
        orch = PipelineOrchestrator(
            steps=["db_check", "codegen"],
            dry_run=True,
            status_file=status_file,
        )
        record = orch.run()

        assert record["status"] == "success"
        assert record["steps_executed"] == ["db_check", "codegen"]
        assert "ingest" not in record["step_results"]

    def test_orchestrator_failure_halts_execution(self, tmp_path: Path) -> None:
        status_file = tmp_path / "fail.json"
        orch = PipelineOrchestrator(
            steps=["db_check", "ingest", "dbt"],
            dry_run=False,
            status_file=status_file,
        )

        with patch.object(
            orch, "step_ingest", return_value=(False, 0.5, "Simulated ingestion failure")
        ):
            record = orch.run()

        assert record["status"] == "partial" or record["status"] == "failed"
        assert "ingest" in record["step_results"]
        assert record["step_results"]["ingest"]["success"] is False
        # dbt should NOT have executed because continue_on_error is False
        assert "dbt" not in record["step_results"]

    def test_orchestrator_continue_on_error(self, tmp_path: Path) -> None:
        status_file = tmp_path / "continue.json"
        orch = PipelineOrchestrator(
            steps=["db_check", "ingest", "codegen"],
            dry_run=False,
            continue_on_error=True,
            status_file=status_file,
        )

        with patch.object(orch, "step_ingest", return_value=(False, 0.2, "Simulated failure")):
            with patch.object(orch, "step_codegen", return_value=(True, 0.1, "Codegen ok")):
                record = orch.run()

        assert record["status"] == "partial"
        assert record["step_results"]["ingest"]["success"] is False
        # Codegen was executed despite ingestion error
        assert record["step_results"]["codegen"]["success"] is True


# ===========================================================================
# 2. Pipeline Health & Observability API Tests
# ===========================================================================


class TestPipelineHealthAPI:
    """Validates the GET /api/health/pipeline endpoint and diagnostic service."""

    def test_get_pipeline_health_success(self, client: TestClient) -> None:
        response = client.get("/api/health/pipeline")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] in ["ok", "warning", "degraded"]
        assert "timestamp" in data
        assert data["database_connected"] is True
        assert data["database_latency_ms"] is not None

        # Table counts
        tc = data["table_counts"]
        assert tc["raw_orders"] == 99441
        assert tc["raw_customers"] in (96096, 99441)
        assert tc["mart_customer_metrics"] == 93358
        assert tc["mart_fact_orders"] in (96478, 99441)
        assert tc["mart_marketing_funnel"] == 8000
        assert tc["ml_rfm_segments"] == 93358
        assert tc["ml_churn_predictions"] == 93358

        # Freshness
        freshness = data["freshness"]
        assert freshness["last_order_timestamp"] is not None
        assert freshness["pipeline_freshness_status"] == "fresh"

        # Model artifact
        model = data["model"]
        assert "artifact_found" in model
        assert "is_trained" in model

        # Anomalies should be a list
        assert isinstance(data["anomalies"], list)

    def test_root_index_contains_pipeline_health_link(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        endpoints = response.json().get("endpoints", {})
        assert "pipeline_health" in endpoints
        assert endpoints["pipeline_health"] == "/api/health/pipeline"

    def test_pipeline_health_anomaly_triggers(self) -> None:
        """Verify that missing tables or unscored customers correctly trigger anomaly alerts."""
        mock_db = MagicMock()
        with patch(
            "backend.services.pipeline_service.check_db_connection",
            return_value={"connected": True, "latency_ms": 1.2},
        ):
            with patch("backend.services.pipeline_service._get_table_counts") as mock_counts:
                from backend.schemas.pipeline import TableCountMetrics

                mock_counts.return_value = TableCountMetrics(
                    raw_orders=1000,
                    raw_customers=1000,
                    mart_customer_metrics=1000,
                    mart_fact_orders=1000,
                    mart_marketing_funnel=500,
                    ml_rfm_segments=1000,
                    ml_churn_predictions=800,  # 200 unscored!
                )
                res = pipeline_service.get_pipeline_health(mock_db)
                assert res.status == "warning"
                assert any("Unscored customers detected" in a for a in res.anomalies)

    def test_pipeline_health_database_offline(self) -> None:
        """Verify behavior when database is offline."""
        mock_db = MagicMock()
        with patch(
            "backend.services.pipeline_service.check_db_connection",
            return_value={"connected": False, "error": "Connection refused"},
        ):
            res = pipeline_service.get_pipeline_health(mock_db)
            assert res.status == "degraded"
            assert res.database_connected is False
            assert any("offline" in a.lower() for a in res.anomalies)
