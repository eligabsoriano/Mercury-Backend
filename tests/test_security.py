"""
tests/test_security.py
======================
Unit and functional test suite for Phase 3:
- Request Tracing (X-Request-ID and X-Process-Time)
- In-memory sliding-window rate limiting
- HMAC-SHA256 JWT security engine
- Header-based API Key & Bearer token authentication
- Public route exemptions
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Generator
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.main import app
from backend.rate_limit import rate_limiter
from backend.security import create_access_token, decode_access_token

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limiter_state() -> Generator[None, None, None]:
    """Ensures rate limiter state is completely fresh for every test."""
    rate_limiter.reset()
    yield
    rate_limiter.reset()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Request Tracing & Performance Middleware
# ─────────────────────────────────────────────────────────────────────────────


def test_request_id_generated_automatically() -> None:
    """Verifies that an incoming request without X-Request-ID gets a unique UUID4 assigned."""
    response = client.get("/")
    assert response.status_code == 200
    req_id = response.headers.get("X-Request-ID")
    assert req_id is not None
    assert len(req_id) >= 16


def test_request_id_preserved_when_provided() -> None:
    """Verifies that an explicitly provided X-Request-ID header is propagated to the response."""
    custom_trace_id = "mercury-trace-client-xyz-987654"
    response = client.get("/", headers={"X-Request-ID": custom_trace_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_trace_id


def test_process_time_header_attached() -> None:
    """Verifies that X-Process-Time is attached with valid millisecond timing."""
    response = client.get("/")
    assert response.status_code == 200
    process_time = response.headers.get("X-Process-Time")
    assert process_time is not None
    # Must match e.g. "1.23ms" or "15.67ms"
    assert re.match(r"^\d+\.\d{2}ms$", process_time)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Rate Limiting Engine & Middleware
# ─────────────────────────────────────────────────────────────────────────────


def test_rate_limiter_sliding_window_permits_below_threshold() -> None:
    """Tests the core rate limiter sliding window allows requests below limit."""
    allowed, remaining, retry_after = rate_limiter.is_allowed(
        "192.168.1.10", limit=5, window_seconds=60
    )
    assert allowed is True
    assert remaining == 4
    assert retry_after == 0


def test_rate_limiter_sliding_window_blocks_over_threshold() -> None:
    """Tests that exceeding the rate limit triggers block and provides retry_after."""
    ip = "192.168.1.20"
    for i in range(3):
        allowed, remaining, _ = rate_limiter.is_allowed(ip, limit=3, window_seconds=60)
        assert allowed is True

    # 4th request must be blocked
    allowed, remaining, retry_after = rate_limiter.is_allowed(ip, limit=3, window_seconds=60)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


def test_rate_limiting_middleware_returns_429() -> None:
    """Verifies that the ASGI middleware catches excessive requests and responds with HTTP 429."""
    settings = get_settings()
    ip_headers = {"X-Forwarded-For": "203.0.113.42"}

    # Temporarily set limit to 3 for testing
    with patch.object(settings, "rate_limit_requests_per_minute", 3):
        for _ in range(3):
            res = client.get("/api/customers?page=1&page_size=1", headers=ip_headers)
            assert res.status_code == 200

        # 4th request should be throttled
        throttled_res = client.get("/api/customers?page=1&page_size=1", headers=ip_headers)
        assert throttled_res.status_code == 429
        data = throttled_res.json()
        assert "Rate limit exceeded" in data["detail"]
        assert throttled_res.headers.get("Retry-After") is not None
        assert throttled_res.headers.get("X-RateLimit-Remaining") == "0"


def test_exempt_paths_not_rate_limited() -> None:
    """Verifies that health checks and root index are exempt from rate limiting."""
    settings = get_settings()
    ip_headers = {"X-Forwarded-For": "203.0.113.99"}

    with patch.object(settings, "rate_limit_requests_per_minute", 2):
        for _ in range(5):
            res = client.get("/health", headers=ip_headers)
            assert res.status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 3. Cryptographic Token Engine (HMAC-SHA256)
# ─────────────────────────────────────────────────────────────────────────────


def test_token_creation_and_decoding() -> None:
    """Tests token generation and round-trip verification with claims."""
    payload = {"sub": "user_42", "scope": "analytics:read"}
    token = create_access_token(payload, expires_delta=timedelta(minutes=30))
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    decoded = decode_access_token(token)
    assert decoded["sub"] == "user_42"
    assert decoded["scope"] == "analytics:read"
    assert decoded["iss"] == "mercury-api"
    assert "exp" in decoded


def test_token_tampered_signature_rejected() -> None:
    """Ensures that modified tokens with bad signatures fail validation with 401."""
    token = create_access_token({"sub": "legit_user"})
    parts = token.split(".")
    tampered_sig = parts[2][:-4] + "AAAA"
    tampered_token = f"{parts[0]}.{parts[1]}.{tampered_sig}"

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(tampered_token)
    assert exc_info.value.status_code == 401
    assert "Invalid token signature" in exc_info.value.detail


def test_expired_token_rejected() -> None:
    """Ensures expired tokens raise 401 Unauthorized."""
    token = create_access_token({"sub": "user_expired"}, expires_delta=timedelta(seconds=-10))

    with pytest.raises(HTTPException) as exc_info:
        decode_access_token(token)
    assert exc_info.value.status_code == 401
    assert "expired" in exc_info.value.detail.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Authentication Enforcements (REQUIRE_AUTH=False vs True)
# ─────────────────────────────────────────────────────────────────────────────


def test_auth_dev_mode_bypass() -> None:
    """When REQUIRE_AUTH=false, callers can access endpoints without credentials."""
    settings = get_settings()
    with patch.object(settings, "require_auth", False):
        res = client.get("/api/auth/me")
        assert res.status_code == 200
        data = res.json()
        assert data["authenticated"] is True
        assert data["auth_type"] == "dev_bypass"


def test_auth_enforced_missing_credentials_returns_401() -> None:
    """When REQUIRE_AUTH=true, missing credentials returns 401 on protected routes."""
    settings = get_settings()
    with patch.object(settings, "require_auth", True):
        res = client.get("/api/auth/me")
        assert res.status_code == 401
        assert "Missing authentication credentials" in res.json()["detail"]


def test_auth_enforced_invalid_api_key_returns_401() -> None:
    """When REQUIRE_AUTH=true, incorrect API Key is rejected."""
    settings = get_settings()
    with patch.object(settings, "require_auth", True):
        res = client.get("/api/auth/me", headers={"X-API-Key": "invalid_bogus_key"})
        assert res.status_code == 401
        assert "Invalid API Key" in res.json()["detail"]


def test_auth_enforced_valid_api_key_accepted() -> None:
    """When REQUIRE_AUTH=true, valid API Key allows access."""
    settings = get_settings()
    valid_key = settings.api_keys[0]
    with patch.object(settings, "require_auth", True):
        res = client.get("/api/auth/me", headers={"X-API-Key": valid_key})
        assert res.status_code == 200
        data = res.json()
        assert data["authenticated"] is True
        assert data["auth_type"] == "api_key"


def test_auth_enforced_valid_bearer_token_accepted() -> None:
    """When REQUIRE_AUTH=true, valid Bearer JWT allows access."""
    settings = get_settings()
    token = create_access_token({"sub": "admin_service", "roles": ["admin"]})
    with patch.object(settings, "require_auth", True):
        res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        data = res.json()
        assert data["authenticated"] is True
        assert data["auth_type"] == "bearer"
        assert data["user"] == "admin_service"


def test_auth_enforced_public_routes_remain_accessible() -> None:
    """Public endpoints remain accessible even when REQUIRE_AUTH=true."""
    settings = get_settings()
    with patch.object(settings, "require_auth", True):
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200


# ─────────────────────────────────────────────────────────────────────────────
# 5. Token Generation Router (/api/auth/token)
# ─────────────────────────────────────────────────────────────────────────────


def test_token_generation_endpoint_success() -> None:
    """Tests POST /api/auth/token issues a valid Bearer token."""
    settings = get_settings()
    valid_key = settings.api_keys[0]
    payload = {
        "client_id": "test_client_app",
        "api_key": valid_key,
        "expires_in_minutes": 30,
    }
    response = client.post("/api/auth/token", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800

    # Validate that the issued token works to authenticate against /api/auth/me
    token = data["access_token"]
    with patch.object(settings, "require_auth", True):
        me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["user"] == "test_client_app"
        assert me_data["auth_type"] == "bearer"


def test_token_generation_with_invalid_key_fails() -> None:
    """Tests POST /api/auth/token with bad API key returns 401."""
    payload = {
        "client_id": "bad_actor",
        "api_key": "wrong_key",
    }
    response = client.post("/api/auth/token", json=payload)
    assert response.status_code == 401
    assert "Invalid API Key" in response.json()["detail"]
