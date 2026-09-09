"""
tests/test_cache.py
===================
Unit test suite for in-memory TTL caching engine and @cached decorator.
Validates thread-safety, monotonic expiration, argument key isolation,
cache bypass mechanics, and transient parameter filtering.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import time
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from backend.cache import (
    InMemoryTTLCache,
    cached,
    clear_cache,
    get_cache,
    get_cache_stats,
    make_cache_key,
)


@pytest.fixture(autouse=True)
def flush_global_cache():
    """Ensure global cache is clean before and after every test."""
    clear_cache()
    yield
    clear_cache()


def test_cache_set_and_get():
    """Verify basic key-value insertion, retrieval, and lookup counters."""
    test_cache = InMemoryTTLCache(max_size=100)
    found, val = test_cache.get("key1")
    assert found is False
    assert val is None

    test_cache.set("key1", {"metric": 123.45}, ttl_seconds=60)
    found, val = test_cache.get("key1")
    assert found is True
    assert val == {"metric": 123.45}

    stats = test_cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["active_items"] == 1


def test_cache_ttl_expiration():
    """Verify entries expire and are purged when TTL elapses."""
    test_cache = InMemoryTTLCache(max_size=100)
    test_cache.set("ephemeral", "data", ttl_seconds=1)

    found, val = test_cache.get("ephemeral")
    assert found is True
    assert val == "data"

    # Simulate clock advance by patching monotonic
    now = time.monotonic()
    with patch("time.monotonic", return_value=now + 2.0):
        found, val = test_cache.get("ephemeral")
        assert found is False
        assert val is None
        assert test_cache.stats()["evictions"] == 1


def test_cache_max_size_and_pruning():
    """Verify capacity limits trigger pruning of expired entries and oldest items."""
    test_cache = InMemoryTTLCache(max_size=3)
    test_cache.set("k1", "v1", ttl_seconds=10)
    test_cache.set("k2", "v2", ttl_seconds=10)
    test_cache.set("k3", "v3", ttl_seconds=10)

    assert test_cache.stats()["active_items"] == 3

    # Adding a 4th key should evict oldest entry to respect max_size
    test_cache.set("k4", "v4", ttl_seconds=10)
    assert test_cache.stats()["active_items"] == 3
    assert test_cache.stats()["evictions"] >= 1


def test_cache_clear():
    """Verify clear flushes all entries."""
    test_cache = InMemoryTTLCache(max_size=100)
    test_cache.set("k1", 1)
    test_cache.set("k2", 2)
    assert test_cache.clear() == 2
    assert test_cache.stats()["active_items"] == 0


def test_cached_decorator_sync():
    """Verify sync function caching prevents redundant computations."""
    call_count = 0

    @cached(ttl=60)
    def calculate_kpi(factor: int, bypass_cache: bool = False) -> int:
        nonlocal call_count
        call_count += 1
        return factor * 10

    # First call: cache miss, computes
    res1 = calculate_kpi(5)
    assert res1 == 50
    assert call_count == 1

    # Second call: cache hit, no re-computation
    res2 = calculate_kpi(5)
    assert res2 == 50
    assert call_count == 1

    # Third call with different arg: cache miss, computes
    res3 = calculate_kpi(6)
    assert res3 == 60
    assert call_count == 2


def test_cached_decorator_bypass():
    """Verify bypass_cache=True forces re-computation and updates cache."""
    call_count = 0

    @cached(ttl=60)
    def query_analytics(bypass_cache: bool = False) -> str:
        nonlocal call_count
        call_count += 1
        return f"result_v{call_count}"

    # First call: computes v1
    assert query_analytics() == "result_v1"
    assert call_count == 1

    # Normal second call: hits cache, returns v1
    assert query_analytics() == "result_v1"
    assert call_count == 1

    # Call with bypass_cache=True: re-computes v2 and refreshes cache
    assert query_analytics(bypass_cache=True) == "result_v2"
    assert call_count == 2

    # Subsequent normal call: returns fresh v2 from updated cache
    assert query_analytics() == "result_v2"
    assert call_count == 2


def test_cached_decorator_ignores_session_and_unhashables():
    """Verify SQLAlchemy sessions and mock objects do not affect cache key generation."""
    call_count = 0

    @cached(ttl=60)
    def fetch_data(db: Session, category: str, bypass_cache: bool = False) -> str:
        nonlocal call_count
        call_count += 1
        return f"{category}_result"

    session1 = MagicMock(spec=Session)
    session2 = MagicMock(spec=Session)

    res1 = fetch_data(session1, "books")
    assert res1 == "books_result"
    assert call_count == 1

    # Second call with completely different session instance must hit cache!
    res2 = fetch_data(session2, "books")
    assert res2 == "books_result"
    assert call_count == 1

    # Verify cache key generated
    key = fetch_data.cache_key(session1, "books")
    assert "books" in key or len(key) > 10


def test_cached_decorator_concurrent_thread_safety():
    """Verify concurrent threads do not race or cause data corruption."""
    compute_count = 0

    @cached(ttl=60)
    def heavy_query(x: int, bypass_cache: bool = False) -> int:
        nonlocal compute_count
        time.sleep(0.01)
        compute_count += 1
        return x * 100

    def worker():
        return heavy_query(7)

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker) for _ in range(20)]
        results = [f.result() for f in futures]

    assert all(r == 700 for r in results)
    # The cache should prevent 20 full recomputations
    assert compute_count < 20


@pytest.mark.asyncio
async def test_cached_decorator_async():
    """Verify coroutine functions wrapped in @cached work seamlessly."""
    call_count = 0

    @cached(ttl=60)
    async def async_fetch(val: int, bypass_cache: bool = False) -> int:
        nonlocal call_count
        await asyncio.sleep(0.01)
        call_count += 1
        return val * 3

    res1 = await async_fetch(10)
    assert res1 == 30
    assert call_count == 1

    res2 = await async_fetch(10)
    assert res2 == 30
    assert call_count == 1

    res3 = await async_fetch(10, bypass_cache=True)
    assert res3 == 30
    assert call_count == 2


def test_cache_disabled_setting():
    """Verify cache bypasses completely when CACHE_ENABLED is False."""
    call_count = 0

    @cached(ttl=60)
    def compute_metric() -> int:
        nonlocal call_count
        call_count += 1
        return call_count

    with patch("backend.cache.get_settings") as mock_settings:
        mock_settings.return_value.cache_enabled = False
        assert compute_metric() == 1
        assert compute_metric() == 2
        assert compute_metric() == 3
