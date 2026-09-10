"""
tests/test_deployment.py
========================
Tests for Phase 4 Containerization & Cloud Deployment artifacts:
- Dockerfile syntax, multi-stage structure, unprivileged user, and HEALTHCHECK
- .dockerignore completeness
- docker-compose.yml validity and service specifications
- Procfile process declaration
- render.yaml blueprint structure
"""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_dockerfile_structure_and_security() -> None:
    """Validates Dockerfile follows security and multi-stage containerization best practices."""
    dockerfile_path = PROJECT_ROOT / "Dockerfile"
    assert dockerfile_path.is_file(), "Dockerfile must exist at repository root"

    content = dockerfile_path.read_text(encoding="utf-8")

    # Multi-stage validation
    assert "FROM python:3.13-slim AS builder" in content
    assert "FROM python:3.13-slim AS runner" in content

    # Virtual environment isolation
    assert "COPY --from=builder /opt/venv /opt/venv" in content
    assert 'ENV PATH="/opt/venv/bin:$PATH"' in content or 'PATH="/opt/venv/bin:$PATH"' in content

    # Unprivileged non-root user (UID 1000)
    assert "useradd -u 1000 -g mercury" in content
    assert "USER mercury" in content

    # Container healthcheck
    assert "HEALTHCHECK" in content
    assert "/health" in content

    # Expose and launch command
    assert "EXPOSE 8000" in content
    assert 'CMD ["uvicorn", "backend.main:app"' in content


def test_dockerignore_exclusions() -> None:
    """Validates .dockerignore excludes virtualenvs, caches, secrets, and raw datasets."""
    dockerignore_path = PROJECT_ROOT / ".dockerignore"
    assert dockerignore_path.is_file(), ".dockerignore must exist at repository root"

    content = dockerignore_path.read_text(encoding="utf-8")
    lines = {
        line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")
    }

    expected_exclusions = [
        ".git/",
        ".venv/",
        "__pycache__/",
        ".pytest_cache/",
        ".env",
        "data/",
        "dataset/",
    ]
    for pattern in expected_exclusions:
        assert pattern in lines, f"Expected {pattern} to be in .dockerignore"


def test_docker_compose_validity() -> None:
    """Validates docker-compose.yml parses cleanly and configures backend service."""
    compose_path = PROJECT_ROOT / "docker-compose.yml"
    assert compose_path.is_file(), "docker-compose.yml must exist at repository root"

    with open(compose_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "services" in data
    assert "backend" in data["services"]

    backend = data["services"]["backend"]
    assert "8000:8000" in backend.get("ports", [])
    assert ".env" in backend.get("env_file", [])
    assert "healthcheck" in backend
    assert "/health" in str(backend["healthcheck"].get("test", ""))


def test_procfile_declaration() -> None:
    """Validates Procfile declares standard web process."""
    procfile_path = PROJECT_ROOT / "Procfile"
    assert procfile_path.is_file(), "Procfile must exist at repository root"

    content = procfile_path.read_text(encoding="utf-8").strip()
    assert content.startswith("web:")
    assert "uvicorn backend.main:app" in content
    assert "$PORT" in content


def test_render_yaml_validity() -> None:
    """Validates render.yaml blueprint syntax and required parameters."""
    render_path = PROJECT_ROOT / "render.yaml"
    assert render_path.is_file(), "render.yaml must exist at repository root"

    with open(render_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "services" in data
    services = data["services"]
    assert len(services) >= 1

    svc = services[0]
    assert svc.get("type") == "web"
    assert svc.get("name") == "mercury-backend"
    assert svc.get("healthCheckPath") == "/health"
    assert "uvicorn backend.main:app" in svc.get("startCommand", "")

    # Check envVars
    env_keys = {ev["key"] for ev in svc.get("envVars", [])}
    assert "DATABASE_URL" in env_keys
    assert "REQUIRE_AUTH" in env_keys
    assert "API_KEYS" in env_keys
