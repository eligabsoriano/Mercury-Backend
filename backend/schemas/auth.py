"""
backend/schemas/auth.py
=======================
Pydantic schemas for authentication requests, token grants, and session identity.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TokenRequest(BaseModel):
    """Payload for requesting an access token."""

    client_id: str = Field(
        default="mercury_client", description="Client or application identifier."
    )
    api_key: Optional[str] = Field(default=None, description="API Key for credential verification.")
    expires_in_minutes: Optional[int] = Field(
        default=60,
        ge=5,
        le=1440,
        description="Desired token lifetime in minutes (5 to 1440).",
    )


class TokenResponse(BaseModel):
    """Token response containing signed JWT and token parameters."""

    access_token: str = Field(..., description="HMAC-SHA256 signed JWT access token.")
    token_type: str = Field(default="bearer", description="Token type, always 'bearer'.")
    expires_in: int = Field(..., description="Token lifespan in seconds.")


class UserIdentity(BaseModel):
    """Authenticated user/client identity representation."""

    authenticated: bool = Field(..., description="Authentication status flag.")
    auth_type: str = Field(
        ..., description="Authentication mechanism ('api_key', 'bearer', 'dev_bypass')."
    )
    user: str = Field(..., description="Identifier of the authenticated subject.")
    roles: List[str] = Field(default_factory=list, description="Assigned role scopes.")
