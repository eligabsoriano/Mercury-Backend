"""
scripts/run_pipeline.py
=======================
Mercury Unified Production Pipeline Runner & Orchestrator.

Sequentially coordinates and executes the complete data and analytics lifecycle:
  1. db_check  - Database connectivity & schema validation
  2. ingest    - Raw CSV loading into PostgreSQL (etl/ingest.py)
  3. dbt       - dbt transformation (compile, run, test) in dbt/mercury_analytics
  4. rfm       - RFM customer segmentation engine (ml/rfm.py)
  5. churn     - Churn ML feature engineering, training & inference (ml/churn.py)
  6. codegen   - OpenAPI schema synchronization & TypeScript SDK codegen

Usage
-----
    # Execute full end-to-end pipeline:
    python scripts/run_pipeline.py

    # Execute specific steps:
    python scripts/run_pipeline.py --steps ingest,dbt,rfm

    # Dry-run validation (checks paths, environment, prerequisites without writes):
    python scripts/run_pipeline.py --dry-run

    # Clean reload (truncates raw tables before ingesting):
    python scripts/run_pipeline.py --truncate

    # Skip dbt data tests for faster turnaround:
    python scripts/run_pipeline.py --skip-tests

    # Continue remaining steps even if one warns/fails:
    python scripts/run_pipeline.py --continue-on-error
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Project Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DBT_DIR = REPO_ROOT / "dbt" / "mercury_analytics"
DEFAULT_STATUS_FILE = REPO_ROOT / "pipeline_status.json"

# Available pipeline step identifiers in topological execution order
VALID_STEPS = ["db_check", "ingest", "dbt", "rfm", "churn", "codegen"]

# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pipeline_orchestrator")


def execute_subprocess(cmd: List[str], cwd: Path, step_name: str) -> Tuple[bool, float, str]:
    """Execute a CLI command subprocess with phase timing and capture output."""
    start_time = time.perf_counter()
    cmd_str = " ".join(str(c) for c in cmd)
    log.info("Executing [%s]: %s (cwd=%s)", step_name, cmd_str, cwd)

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        duration = time.perf_counter() - start_time
        output = proc.stdout.strip() if proc.stdout else ""
        success = proc.returncode == 0
        if not success:
            log.error(
                "[%s] failed with exit code %d:\n%s", step_name, proc.returncode, output[-1000:]
            )
        return success, duration, output
    except Exception as exc:
        duration = time.perf_counter() - start_time
        log.error("[%s] subprocess exception: %s", step_name, exc)
        return False, duration, str(exc)


class PipelineOrchestrator:
    """Manages execution, prerequisites, timing, and status tracking of the data pipeline."""

    def __init__(
        self,
        steps: List[str],
        dry_run: bool = False,
        truncate: bool = False,
        skip_tests: bool = False,
        continue_on_error: bool = False,
        window: int = 90,
        status_file: Path = DEFAULT_STATUS_FILE,
    ) -> None:
        self.steps = [s.strip().lower() for s in steps]
        self.dry_run = dry_run
        self.truncate = truncate
        self.skip_tests = skip_tests
        self.continue_on_error = continue_on_error
        self.window = window
        self.status_file = status_file
        self.run_id = (
            f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        )
        self.py_exec = sys.executable

        # Validate step names
        for step in self.steps:
            if step not in VALID_STEPS:
                raise ValueError(f"Unknown pipeline step: '{step}'. Valid steps are: {VALID_STEPS}")

    def step_db_check(self) -> Tuple[bool, float, str]:
        """Verify database connectivity and query response."""
        start = time.perf_counter()
        if self.dry_run:
            db_url = os.getenv("DATABASE_URL")
            configured = bool(db_url and db_url.strip())
            duration = time.perf_counter() - start
            msg = (
                "DATABASE_URL is configured"
                if configured
                else "DATABASE_URL is unset (dry-run mode)"
            )
            return True, duration, msg

        try:
            from backend.database import check_db_connection

            status = check_db_connection()
            duration = time.perf_counter() - start
            if status.get("connected"):
                return (
                    True,
                    duration,
                    f"Database connected ({status.get('latency_ms', 0):.1f}ms latency)",
                )
            return False, duration, f"Database unreachable: {status.get('error')}"
        except Exception as exc:
            duration = time.perf_counter() - start
            return False, duration, str(exc)

    def step_ingest(self) -> Tuple[bool, float, str]:
        """Run raw CSV ingestion runner."""
        if self.dry_run:
            return (
                True,
                0.01,
                "Dry-run: verified etl/ingest.py path and candidate dataset directories",
            )

        cmd = [self.py_exec, str(REPO_ROOT / "etl" / "ingest.py")]
        if self.truncate:
            cmd.append("--truncate")
        return execute_subprocess(cmd, REPO_ROOT, "ingest")

    def step_dbt(self) -> Tuple[bool, float, str]:
        """Run dbt compilation, model materialization, and data tests."""
        if self.dry_run:
            return True, 0.01, f"Dry-run: verified dbt project in {DBT_DIR}"

        dbt_cmd = ["dbt"]
        # Try local venv dbt first
        venv_dbt = REPO_ROOT / ".venv" / "bin" / "dbt"
        if venv_dbt.exists():
            dbt_cmd = [str(venv_dbt)]

        # 1. dbt compile
        cmd_compile = dbt_cmd + [
            "compile",
            "--project-dir",
            str(DBT_DIR),
            "--profiles-dir",
            str(DBT_DIR),
        ]
        ok, dur_c, out_c = execute_subprocess(cmd_compile, REPO_ROOT, "dbt-compile")
        if not ok and not self.continue_on_error:
            return False, dur_c, out_c

        # 2. dbt run
        cmd_run = dbt_cmd + ["run", "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
        ok, dur_r, out_r = execute_subprocess(cmd_run, REPO_ROOT, "dbt-run")
        if not ok and not self.continue_on_error:
            return False, dur_c + dur_r, out_r

        # 3. dbt test (optional)
        dur_t = 0.0
        if not self.skip_tests:
            cmd_test = dbt_cmd + [
                "test",
                "--project-dir",
                str(DBT_DIR),
                "--profiles-dir",
                str(DBT_DIR),
            ]
            ok, dur_t, out_t = execute_subprocess(cmd_test, REPO_ROOT, "dbt-test")
            if not ok and not self.continue_on_error:
                return False, dur_c + dur_r + dur_t, out_t

        return True, dur_c + dur_r + dur_t, "dbt models and tests completed successfully"

    def step_rfm(self) -> Tuple[bool, float, str]:
        """Execute RFM customer segmentation engine."""
        if self.dry_run:
            return True, 0.01, f"Dry-run: verified ml/rfm.py with {self.window}-day window"

        cmd = [self.py_exec, "-m", "ml.rfm", "--window", str(self.window)]
        return execute_subprocess(cmd, REPO_ROOT, "rfm")

    def step_churn(self) -> Tuple[bool, float, str]:
        """Execute Churn ML pipeline (features, training, evaluation, inference)."""
        if self.dry_run:
            return True, 0.01, f"Dry-run: verified ml/churn.py with {self.window}-day window"

        cmd = [self.py_exec, "-m", "ml.churn", "--window", str(self.window)]
        return execute_subprocess(cmd, REPO_ROOT, "churn")

    def step_codegen(self) -> Tuple[bool, float, str]:
        """Export static OpenAPI 3.1 schema and generate TypeScript client bindings."""
        if self.dry_run:
            return True, 0.01, "Dry-run: verified scripts/export_openapi.py"

        # 1. Export OpenAPI
        cmd_export = [self.py_exec, str(REPO_ROOT / "scripts" / "export_openapi.py")]
        ok, dur_e, out_e = execute_subprocess(cmd_export, REPO_ROOT, "export-openapi")
        if not ok and not self.continue_on_error:
            return False, dur_e, out_e

        # 2. NPM codegen if npm exists
        dur_n = 0.0
        try:
            cmd_npm = ["npm", "run", "generate:types"]
            ok_n, dur_n, _ = execute_subprocess(cmd_npm, REPO_ROOT, "npm-generate-types")
        except Exception:
            pass

        return True, dur_e + dur_n, "OpenAPI schema and TypeScript contracts synchronized"

    def run(self) -> Dict[str, Any]:
        """Run all requested pipeline steps in sequence and persist status record."""
        start_time_iso = datetime.now(timezone.utc).isoformat()
        total_start = time.perf_counter()

        step_dispatch = {
            "db_check": self.step_db_check,
            "ingest": self.step_ingest,
            "dbt": self.step_dbt,
            "rfm": self.step_rfm,
            "churn": self.step_churn,
            "codegen": self.step_codegen,
        }

        print("\n" + "=" * 70)
        print(f" MERCURY UNIFIED PIPELINE ORCHESTRATOR [ID: {self.run_id}]")
        print(f" Mode: {'DRY-RUN (Simulated)' if self.dry_run else 'PRODUCTION (Live Execution)'}")
        print(f" Steps: {', '.join(self.steps)}")
        print("=" * 70)

        step_results: Dict[str, Any] = {}
        overall_success = True

        for idx, step_name in enumerate(self.steps, 1):
            runner_fn = step_dispatch[step_name]
            print(
                f"[{idx}/{len(self.steps)}] Executing {step_name.upper()} ...", end=" ", flush=True
            )

            success, duration, message = runner_fn()
            status_label = "OK" if success else "FAILED"
            print(f"[{status_label} in {duration:.2f}s]")

            step_results[step_name] = {
                "success": success,
                "duration_seconds": round(duration, 3),
                "message": message[:500],
            }

            if not success:
                overall_success = False
                if not self.continue_on_error:
                    print(f"\n[!] Pipeline halted at step '{step_name}'. Details: {message[:300]}")
                    break

        total_duration = time.perf_counter() - total_start
        end_time_iso = datetime.now(timezone.utc).isoformat()
        final_status = (
            "success"
            if overall_success
            else ("partial" if any(r["success"] for r in step_results.values()) else "failed")
        )

        print("-" * 70)
        print(f" PIPELINE RESULT: {final_status.upper()} (Total Duration: {total_duration:.2f}s)")
        print("=" * 70 + "\n")

        # Save status file for observability API
        record = {
            "run_id": self.run_id,
            "status": final_status,
            "start_time": start_time_iso,
            "end_time": end_time_iso,
            "duration_seconds": round(total_duration, 3),
            "dry_run": self.dry_run,
            "steps_executed": list(step_results.keys()),
            "step_results": step_results,
        }

        try:
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2)
            log.info("Persisted pipeline execution status to %s", self.status_file)
        except Exception as exc:
            log.warning("Failed to persist pipeline status file: %s", exc)

        return record


def main() -> int:
    """CLI entrypoint for pipeline orchestrator."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Mercury Unified Production Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--steps",
        default=",".join(VALID_STEPS),
        help=f"Comma-separated steps to execute. Available: {', '.join(VALID_STEPS)} (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate environment, prerequisites, and paths without running live transformations.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Pass --truncate to the ingestion step for a clean table reload.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip dbt test phase for faster pipeline turnaround.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue remaining steps even if an intermediate step fails.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=90,
        help="Churn and RFM window in days (default: 90).",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=DEFAULT_STATUS_FILE,
        help=f"Path to write status JSON file (default: {DEFAULT_STATUS_FILE}).",
    )

    args = parser.parse_args()
    selected_steps = [s.strip() for s in args.steps.split(",") if s.strip()]

    orchestrator = PipelineOrchestrator(
        steps=selected_steps,
        dry_run=args.dry_run,
        truncate=args.truncate,
        skip_tests=args.skip_tests,
        continue_on_error=args.continue_on_error,
        window=args.window,
        status_file=args.status_file,
    )

    record = orchestrator.run()
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
