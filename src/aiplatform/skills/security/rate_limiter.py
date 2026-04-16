"""
Token-bucket rate limiter for outbound HTTP requests in active scanning phases.

Usage:
    limiter = RateLimiter(max_rps=2.0)
    limiter.acquire()   # blocks until a token is available
    requests.get(url)
"""

import threading
import time


class RateLimiter:
    """
    Thread-safe token bucket.  Callers invoke `acquire()` before each
    outbound request; the call blocks for the minimum time needed to
    stay within the configured rate.

    Args:
        max_rps: Maximum requests per second (float). Default 2.
    """

    def __init__(self, max_rps: float = 2.0) -> None:
        if max_rps <= 0:
            raise ValueError("max_rps must be positive")
        self._rate = max_rps
        self._tokens: float = max_rps      # start with a full bucket
        self._last: float = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        """Block until one token is available, then consume it."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            # Refill tokens based on elapsed time, capped at bucket size
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
            else:
                # Need to wait until we accumulate another token
                wait = (1.0 - self._tokens) / self._rate
                time.sleep(wait)
                self._tokens = 0.0
                self._last = time.monotonic()
