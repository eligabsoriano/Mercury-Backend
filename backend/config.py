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

        # Database connection URL
        self.database_url: str = os.getenv("DATABASE_URL", "")

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
