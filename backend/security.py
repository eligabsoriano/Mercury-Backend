"""
backend/security.py
===================
Authentication and security dependencies for Mercury API.
Supports:
- Header-based API key: X-API-Key
- Bearer token: Authorization: Bearer <token> (HMAC-SHA256 JWT)
- Configurable requirement: REQUIRE_AUTH=false in dev, true in production
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from datetime import timedelta
from typing import Any, Dict, Optional, Set

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from backend.config import get_settings

log = logging.getLogger("mercury.security")
settings = get_settings()

# Security schemes for Swagger UI and FastAPI dependency injection
api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
http_bearer_scheme = HTTPBearer(auto_error=False)

# Public endpoints exempted from mandatory authentication even when REQUIRE_AUTH=True
EXEMPT_PATHS: Set[str] = {
    "/",
    "/health",
    "/api/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/auth/token",
}


def _b64encode(data: bytes) -> str:
    """URL-safe base64 encoding without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data_str: str) -> bytes:
    """URL-safe base64 decoding with padding restoration."""
    rem = len(data_str) % 4
    if rem > 0:
        data_str += "=" * (4 - rem)
    return base64.urlsafe_b64decode(data_str.encode("ascii"))


def create_access_token(
    payload: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
    secret_key: Optional[str] = None,
) -> str:
    """
    Creates an HMAC-SHA256 signed JWT string with standard claims.
    """
    key = secret_key or settings.jwt_secret_key
    now = int(time.time())
    if expires_delta:
        exp = now + int(expires_delta.total_seconds())
    else:
        exp = now + (settings.jwt_access_token_expire_minutes * 60)

    token_claims = {
        "iss": "mercury-api",
        "iat": now,
        "exp": exp,
        **payload,
    }

    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}

    header_bytes = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_bytes = json.dumps(token_claims, separators=(",", ":"), sort_keys=True).encode("utf-8")

    header_b64 = _b64encode(header_bytes)
    payload_b64 = _b64encode(payload_bytes)

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    sig_b64 = _b64encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Validates signature, structure, and expiration of an HMAC-SHA256 token.
    Raises HTTPException(401) on any failure.
    """
    key = secret_key or settings.jwt_secret_key
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token: expected 3-part JWT structure",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    header_b64, payload_b64, sig_b64 = parts

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()

    try:
        provided_sig = _b64decode(sig_b64)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature encoding",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    if not hmac.compare_digest(expected_sig, provided_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    try:
        payload_bytes = _b64decode(payload_b64)
        claims = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Corrupt token claims payload",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        )

    # Expiration check
    exp = claims.get("exp")
    if exp is not None and time.time() > float(exp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"Token expired\""},
        )

    return claims


def is_path_exempt(path: str) -> bool:
    """Checks whether an incoming request path is exempt from authentication."""
    clean_path = path.rstrip("/") if path != "/" else "/"
    return clean_path in EXEMPT_PATHS or path.startswith("/docs") or path.startswith("/redoc")


async def verify_auth(
    request: Request,
    api_key_header: Optional[str] = Security(api_key_header_scheme),
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(http_bearer_scheme),
) -> Dict[str, Any]:
    """
    FastAPI security dependency for route-level or global authentication.
    - If REQUIRE_AUTH=false: allows request and yields dev context.
    - If path is exempt (e.g. /health, /docs): allows request.
    - Otherwise requires valid X-API-Key or valid Bearer JWT.
    """
    req_settings = get_settings()

    # Public endpoint exemption
    if is_path_exempt(request.url.path):
        user_ctx = {"authenticated": True, "auth_type": "public", "user": "anonymous", "roles": ["public"]}
        request.state.user = user_ctx
        return user_ctx

    # Development bypass when REQUIRE_AUTH is false
    if not req_settings.require_auth:
        user_ctx = {"authenticated": True, "auth_type": "dev_bypass", "user": "developer", "roles": ["admin"]}
        request.state.user = user_ctx
        return user_ctx

    # Header-based API Key authentication
    if api_key_header:
        header_key = api_key_header.strip()
        is_valid = any(hmac.compare_digest(header_key, k) for k in req_settings.api_keys)
        if is_valid:
            user_ctx = {
                "authenticated": True,
                "auth_type": "api_key",
                "user": f"api_client_{header_key[:6]}",
                "roles": ["api_consumer"],
            }
            request.state.user = user_ctx
            return user_ctx
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key provided in X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Bearer JWT token authentication
    if bearer_creds and bearer_creds.credentials:
        claims = decode_access_token(bearer_creds.credentials, secret_key=req_settings.jwt_secret_key)
        user_ctx = {
            "authenticated": True,
            "auth_type": "bearer",
            "user": claims.get("sub", "authenticated_user"),
            "claims": claims,
            "roles": claims.get("roles", ["user"]),
        }
        request.state.user = user_ctx
        return user_ctx

    # No credentials provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials. Provide 'X-API-Key' header or 'Authorization: Bearer <token>'",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(auth_context: Dict[str, Any] = Depends(verify_auth)) -> Dict[str, Any]:
    """Dependency helper to inject the validated authentication context."""
    return auth_context
