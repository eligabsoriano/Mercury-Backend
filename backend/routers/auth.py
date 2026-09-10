"""
backend/routers/auth.py
======================
Authentication router: token generation and identity inspection.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from backend.config import get_settings
from backend.schemas.auth import TokenRequest, TokenResponse, UserIdentity
from backend.security import create_access_token, get_current_user

auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])
settings = get_settings()


@auth_router.post(
    "/token",
    response_model=TokenResponse,
    summary="Generate Bearer Access Token",
    description="Issues an HMAC-SHA256 signed JWT Bearer token valid for API access.",
)
def generate_token(request_data: TokenRequest) -> TokenResponse:
    """Generates an access token given valid client credentials or during dev mode."""
    req_settings = get_settings()

    # Validate API Key if provided
    if request_data.api_key:
        valid_key = any(request_data.api_key == k for k in req_settings.api_keys)
        if not valid_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key provided",
                headers={"WWW-Authenticate": "ApiKey"},
            )
    elif req_settings.require_auth:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key required to issue access tokens in authenticated environment",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    lifetime_minutes = request_data.expires_in_minutes or 60
    expires_delta = timedelta(minutes=lifetime_minutes)

    claims = {
        "sub": request_data.client_id or "mercury_client",
        "roles": ["api_consumer"],
    }

    token = create_access_token(
        claims,
        expires_delta=expires_delta,
        secret_key=req_settings.jwt_secret_key,
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=lifetime_minutes * 60,
    )


@auth_router.get(
    "/me",
    response_model=UserIdentity,
    summary="Get Current Authentication Identity",
    description="Returns identity and scope details for the currently authenticated caller.",
)
def get_auth_identity(current_user: Dict[str, Any] = Depends(get_current_user)) -> UserIdentity:
    """Returns caller profile and authentication metadata."""
    return UserIdentity(
        authenticated=current_user.get("authenticated", False),
        auth_type=current_user.get("auth_type", "unknown"),
        user=current_user.get("user", "anonymous"),
        roles=current_user.get("roles", []),
    )
