"""
backend/config.py
=================
Application configuration and environment settings for Mercury API.
Reads configuration from environment variables or .env file.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Ensure .env is loaded from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")


class Settings:
    """Application runtime settings and environment configuration."""

    def __init__(self) -> None:
        self.app_name: str = os.getenv("APP_NAME", "Mercury Customer Intelligence API")
        self.app_version: str = os.getenv("APP_VERSION", "1.0.0")
        self.app_description: str = os.getenv(
            "APP_DESCRIPTION",
            "Customer intelligence, RFM segmentation, churn prediction, "
            "and revenue-at-risk retention analytics platform.",
        )
        self.env: str = os.getenv("ENV", "development").lower()
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))

        # Database connection and pool settings
        self.database_url: str = os.getenv("DATABASE_URL", "")
        self.db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "10"))
        self.db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        self.db_pool_recycle: int = int(os.getenv("DB_POOL_RECYCLE", "300"))
        self.db_pool_timeout: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))

        # In-memory TTL caching configuration
        self.cache_enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        self.cache_default_ttl: int = int(os.getenv("CACHE_DEFAULT_TTL_SECONDS", "300"))

        # Security & Authentication settings
        self.require_auth: bool = os.getenv("REQUIRE_AUTH", "false").lower() in ("true", "1", "yes")
        raw_api_keys = os.getenv("API_KEYS", "mercury_test_api_key_12345,mercury_admin_key_67890")
        self.api_keys: List[str] = [k.strip() for k in raw_api_keys.split(",") if k.strip()]
        self.jwt_secret_key: str = os.getenv(
            "JWT_SECRET_KEY", "mercury-super-secret-production-key-change-me"
        )
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_access_token_expire_minutes: int = int(
            os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )

        # Rate limiting settings
        self.rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        self.rate_limit_requests_per_minute: int = int(
            os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "120")
        )

        # CORS configuration
        raw_origins = os.getenv("CORS_ORIGINS", "*")
        if raw_origins == "*":
            self.cors_origins: List[str] = ["*"]
        else:
            self.cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env in ("production", "prod")

    @property
    def is_development(self) -> bool:
        return not self.is_production


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
