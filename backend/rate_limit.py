"""
backend/rate_limit.py
=====================
Thread-safe sliding-window rate limiting engine for Mercury API.
Protects endpoints against flooding and protects database connection pools.
"""

from __future__ import annotations

import collections
import logging
import threading
import time
from typing import Deque, Dict, Optional, Tuple

from starlette.requests import Request

from backend.config import get_settings

log = logging.getLogger("mercury.rate_limit")
settings = get_settings()


class SlidingWindowRateLimiter:
    """
    Sliding window log rate limiter using high-resolution monotonic timestamps.
    Thread-safe via RLock.
    """

    def __init__(self, default_limit: int = 120, window_seconds: int = 60) -> None:
        self.default_limit = default_limit
        self.window_seconds = window_seconds
        self._lock = threading.RLock()
        self._records: Dict[str, Deque[float]] = collections.defaultdict(collections.deque)
        self._last_cleanup = time.monotonic()

    def is_allowed(
        self,
        identifier: str,
        limit: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> Tuple[bool, int, int]:
        """
        Evaluates whether a request from `identifier` is permitted.

        Returns:
            (is_allowed: bool, remaining_requests: int, retry_after_seconds: int)
        """
        max_requests = limit if limit is not None else self.default_limit
        window = window_seconds if window_seconds is not None else self.window_seconds
        now = time.monotonic()
        cutoff = now - window

        with self._lock:
            # Periodic cleanup of empty or inactive records every 5 minutes
            if now - self._last_cleanup > 300:
                self._cleanup_stale_records(now, window)
                self._last_cleanup = now

            timestamps = self._records[identifier]

            # Pop timestamps that have aged out of the sliding window
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            current_count = len(timestamps)

            if current_count >= max_requests:
                # Rate limit exceeded; calculate seconds until the oldest timestamp slides out
                oldest_timestamp = timestamps[0]
                retry_after = max(1, int(oldest_timestamp + window - now))
                return False, 0, retry_after

            # Allow request and append current timestamp
            timestamps.append(now)
            remaining = max(0, max_requests - len(timestamps))
            return True, remaining, 0

    def _cleanup_stale_records(self, now: float, window: int) -> None:
        """Removes entries that have had no traffic within the window."""
        cutoff = now - window
        stale_keys = [k for k, q in self._records.items() if not q or q[-1] < cutoff]
        for k in stale_keys:
            del self._records[k]

    def reset(self, identifier: Optional[str] = None) -> None:
        """Resets rate limit counter for a specific identifier or all identifiers."""
        with self._lock:
            if identifier:
                self._records.pop(identifier, None)
            else:
                self._records.clear()


# Global rate limiter instance initialized with settings
rate_limiter = SlidingWindowRateLimiter(
    default_limit=settings.rate_limit_requests_per_minute,
    window_seconds=60,
)


def get_client_ip(request: Request) -> str:
    """
    Extracts the client IP address from the request.
    When trust_proxy_headers is enabled, inspects X-Forwarded-For (first hop) and X-Real-IP.
    Otherwise falls back directly to request.client.host to prevent spoofing in direct deployments.
    """
    req_settings = get_settings()
    if req_settings.trust_proxy_headers:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
            if client_ip:
                return client_ip

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"
