"""
tests/test_ci.py
================
Tests for Phase 5 Automated CI/CD Pipeline:
- .github/workflows/ci.yml YAML validity
- Trigger definitions (push and pull_request on main)
- Setup Python 3.13 with pip caching
- Ruff lint and format check steps
- Pytest execution step
"""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_ci_workflow_exists_and_parses() -> None:
    """Verifies that ci.yml exists and parses as valid YAML."""
    ci_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_path.is_file(), "ci.yml must exist under .github/workflows/"

    with open(ci_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    assert "on" in workflow, "Workflow must define triggers"
    assert "jobs" in workflow, "Workflow must define jobs"


def test_ci_workflow_triggers() -> None:
    """Verifies that the workflow is triggered on push and PR to main."""
    ci_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    with open(ci_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    triggers = workflow.get("on", {})
    assert "push" in triggers, "Push trigger must be configured"
    assert "main" in triggers["push"].get("branches", []), "Push trigger must monitor 'main' branch"

    assert "pull_request" in triggers, "Pull Request trigger must be configured"
    assert "main" in triggers["pull_request"].get("branches", []), (
        "PR trigger must monitor 'main' branch"
    )


def test_ci_workflow_steps() -> None:
    """Verifies that all required quality gates and test steps are present."""
    ci_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    with open(ci_path, "r", encoding="utf-8") as f:
        workflow = yaml.safe_load(f)

    jobs = workflow.get("jobs", {})
    assert len(jobs) >= 1

    first_job = next(iter(jobs.values()))
    steps = first_job.get("steps", [])
    step_runs = [s.get("run", "") for s in steps if "run" in s]
    step_uses = [s.get("uses", "") for s in steps if "uses" in s]

    # Checkout
    assert any("actions/checkout" in u for u in step_uses)

    # Python 3.13 setup
    python_step = next(s for s in steps if "actions/setup-python" in s.get("uses", ""))
    assert str(python_step.get("with", {}).get("python-version")) == "3.13"
    assert python_step.get("with", {}).get("cache") == "pip"

    # Ruff check
    assert any("ruff check backend/ ml/ tests/" in r for r in step_runs)

    # Ruff format check
    assert any("ruff format --check backend/ ml/ tests/" in r for r in step_runs)

    # Pytest execution
    assert any("pytest tests/ -v" in r for r in step_runs)
