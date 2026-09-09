"""
backend/cache.py
================
High-performance, thread-safe in-memory TTL (Time-To-Live) caching engine.
Designed for low-latency macro analytics queries across 90k+ customer metrics.

Features:
- Thread-safe read/write operations protected by re-entrant locks (threading.RLock).
- Monotonic clock-based expiration to prevent clock drift issues.
- Automatic filtering of transient/unhashable objects (SQLAlchemy Session, Request, Response).
- First-class support for `bypass_cache=True` to force fresh database recomputations.
- Function decorator `@cached` supporting both synchronous and asynchronous functions.
- Detailed cache telemetry (hits, misses, bypasses, evictions, memory pruning).
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import inspect
import json
import logging
import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Dict, Optional, Tuple

from backend.config import get_settings

log = logging.getLogger("mercury.cache")


@dataclass
class CacheEntry:
    """Represents a cached item with absolute monotonic expiry and metadata."""

    value: Any
    expires_at: float
    created_at: float
    hit_count: int = 0

    def is_expired(self, now: Optional[float] = None) -> bool:
        current_time = now if now is not None else time.monotonic()
        return current_time >= self.expires_at


class InMemoryTTLCache:
    """
    Thread-safe in-memory cache with monotonic TTL expiration and LRU capacity protection.
    """

    def __init__(self, max_size: int = 5000) -> None:
        self.max_size = max_size
        self._store: Dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._hits: int = 0
        self._misses: int = 0
        self._bypasses: int = 0
        self._evictions: int = 0

    def get(self, key: str) -> Tuple[bool, Any]:
        """
        Retrieve a value from the cache.
        Returns a tuple of (found: bool, value: Any).
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return False, None

            now = time.monotonic()
            if entry.is_expired(now):
                del self._store[key]
                self._evictions += 1
                self._misses += 1
                return False, None

            entry.hit_count += 1
            self._hits += 1
            return True, entry.value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """
        Store a value in the cache with a specified TTL in seconds.
        If ttl_seconds is None, uses the application default TTL from settings.
        """
        settings = get_settings()
        ttl = ttl_seconds if ttl_seconds is not None else settings.cache_default_ttl
        now = time.monotonic()
        expires_at = now + max(1, ttl)

        with self._lock:
            # If capacity is exceeded, prune expired entries first
            if len(self._store) >= self.max_size and key not in self._store:
                self._prune_expired_locked(now)

                # If still over capacity, evict least recently used/oldest entry
                if len(self._store) >= self.max_size:
                    oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
                    del self._store[oldest_key]
                    self._evictions += 1

            self._store[key] = CacheEntry(
                value=value,
                expires_at=expires_at,
                created_at=now,
                hit_count=0,
            )

    def record_bypass(self) -> None:
        """Increment bypass counter when a request explicitly requests fresh data."""
        with self._lock:
            self._bypasses += 1

    def delete(self, key: str) -> bool:
        """Remove a specific key from the cache."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> int:
        """Clear all entries from the cache and return the number of items removed."""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def prune_expired(self) -> int:
        """Prune all expired entries from cache and return count of pruned entries."""
        with self._lock:
            return self._prune_expired_locked(time.monotonic())

    def _prune_expired_locked(self, now: float) -> int:
        """Internal helper for pruning while holding the lock."""
        expired_keys = [k for k, v in self._store.items() if v.is_expired(now)]
        for k in expired_keys:
            del self._store[k]
        self._evictions += len(expired_keys)
        return len(expired_keys)

    def stats(self) -> Dict[str, Any]:
        """Return cache performance statistics and health metrics."""
        with self._lock:
            total_lookups = self._hits + self._misses
            hit_ratio = round((self._hits / total_lookups) * 100.0, 2) if total_lookups > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "bypasses": self._bypasses,
                "evictions": self._evictions,
                "total_lookups": total_lookups,
                "hit_ratio_pct": hit_ratio,
                "active_items": len(self._store),
                "max_size": self.max_size,
            }


# Global singleton cache instance
cache = InMemoryTTLCache()


def get_cache() -> InMemoryTTLCache:
    """Getter for the global cache instance."""
    return cache


def clear_cache() -> int:
    """Convenience helper to flush the global cache."""
    return cache.clear()


def get_cache_stats() -> Dict[str, Any]:
    """Convenience helper to inspect global cache metrics."""
    return cache.stats()


def _is_unhashable_or_transient(obj: Any) -> bool:
    """
    Check if an argument is a transient or unhashable request context object
    (such as SQLAlchemy Session, FastAPI Request/Response) that should be excluded
    from the deterministic cache key.
    """
    try:
        from sqlalchemy.orm import Session
        if isinstance(obj, Session):
            return True
    except ImportError:
        pass

    type_name = type(obj).__name__
    module_name = type(obj).__module__ or ""

    if "sqlalchemy" in module_name or "Session" in type_name:
        return True
    if "starlette" in module_name or "fastapi" in module_name:
        if type_name in ("Request", "Response", "BackgroundTasks"):
            return True
    return False


def make_cache_key(func: Callable, args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> str:
    """
    Generate a deterministic, isolated cache key for a given function call.
    Filters out database sessions and the `bypass_cache` flag so that bypass operations
    correctly overwrite the exact canonical key.
    """
    sig = inspect.signature(func)
    bound = sig.bind_partial(*args, **kwargs)

    filtered_args: Dict[str, Any] = {}
    for param_name, value in bound.arguments.items():
        # Exclude self or cls parameter for cleaner keys
        if param_name in ("self", "cls"):
            continue
        # Exclude bypass_cache flag so both cached and bypass calls refer to same key
        if param_name == "bypass_cache":
            continue
        # Exclude common database session and request param names
        if param_name.lower() in ("db", "session", "db_session", "request", "response", "background_tasks"):
            continue
        # Exclude transient database sessions and HTTP objects
        if _is_unhashable_or_transient(value):
            continue

        try:
            # Verify serialization safety
            json.dumps(value, sort_keys=True, default=str)
            filtered_args[param_name] = value
        except Exception:
            filtered_args[param_name] = str(value)

    serialized_params = json.dumps(filtered_args, sort_keys=True, default=str)
    param_hash = hashlib.sha256(serialized_params.encode("utf-8")).hexdigest()[:16]
    return f"{func.__module__}:{func.__qualname__}:{param_hash}"


def cached(
    ttl: Optional[int] = None,
    key_builder: Optional[Callable[..., str]] = None,
) -> Callable:
    """
    Decorator to cache function results in memory with a configurable TTL.

    Supports:
    - Synchronous (`def`) and asynchronous (`async def`) functions.
    - Automatic `bypass_cache: bool = True` detection to force fresh compute.
    - Exposes `.cache_clear()` on decorated functions.

    Usage:
        @cached(ttl=300)
        def get_portfolio_overview(db: Session, bypass_cache: bool = False):
            ...
    """

    def decorator(fn: Callable) -> Callable:
        is_coroutine = asyncio.iscoroutinefunction(fn)
        effective_key_builder = key_builder or make_cache_key

        if is_coroutine:

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                settings = get_settings()
                if not settings.cache_enabled:
                    return await fn(*args, **kwargs)

                bypass = kwargs.get("bypass_cache", False)
                key = effective_key_builder(fn, args, kwargs)

                if bypass:
                    cache.record_bypass()
                    log.debug("Cache BYPASS requested for key %s", key)
                    result = await fn(*args, **kwargs)
                    cache.set(key, result, ttl_seconds=ttl)
                    return result

                found, cached_val = cache.get(key)
                if found:
                    log.debug("Cache HIT for key %s", key)
                    return cached_val

                log.debug("Cache MISS for key %s", key)
                result = await fn(*args, **kwargs)
                cache.set(key, result, ttl_seconds=ttl)
                return result

            async_wrapper.cache_clear = lambda: cache.clear()
            async_wrapper.cache_key = lambda *a, **kw: effective_key_builder(fn, a, kw)
            return async_wrapper

        else:

            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                settings = get_settings()
                if not settings.cache_enabled:
                    return fn(*args, **kwargs)

                bypass = kwargs.get("bypass_cache", False)
                key = effective_key_builder(fn, args, kwargs)

                if bypass:
                    cache.record_bypass()
                    log.debug("Cache BYPASS requested for key %s", key)
                    result = fn(*args, **kwargs)
                    cache.set(key, result, ttl_seconds=ttl)
                    return result

                found, cached_val = cache.get(key)
                if found:
                    log.debug("Cache HIT for key %s", key)
                    return cached_val

                log.debug("Cache MISS for key %s", key)
                result = fn(*args, **kwargs)
                cache.set(key, result, ttl_seconds=ttl)
                return result

            sync_wrapper.cache_clear = lambda: cache.clear()
            sync_wrapper.cache_key = lambda *a, **kw: effective_key_builder(fn, a, kw)
            return sync_wrapper

    return decorator
