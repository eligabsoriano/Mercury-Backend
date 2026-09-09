"""
backend/database.py
===================
SQLAlchemy database engine, session management, and FastAPI dependency.
Configured with connection pooling optimized for Neon PostgreSQL.
"""

from __future__ import annotations

import logging
import time
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.config import get_settings

log = logging.getLogger(__name__)

settings = get_settings()

if not settings.database_url:
    log.warning("DATABASE_URL environment variable is not set!")

# Neon / PostgreSQL connection pool settings:
# - pool_pre_ping ensures stale/closed connections from serverless sleep are refreshed.
# - pool_recycle prevents stale connections by recycling connections (default 300s).
# - pool_size & max_overflow scaled for high-concurrency analytical throughput.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=settings.db_pool_recycle,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a transactional SQLAlchemy session.
    Automatically closes the session after the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> dict:
    """
    Utility to verify live database connectivity and latency.
    Returns a status dict: {"connected": bool, "latency_ms": float, "error": str | None}.
    """
    start_time = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {"connected": True, "latency_ms": latency_ms, "error": None}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        log.error("Database connection check failed: %s", exc)
        return {"connected": False, "latency_ms": latency_ms, "error": str(exc)}
