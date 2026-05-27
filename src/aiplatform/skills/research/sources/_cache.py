"""
Tiny cache + counter used by the Apify runner for result caching and a daily
cost cap. Redis-backed (REDIS_URL) so it is shared across worker processes, with
an in-process fallback for tests/local runs where Redis is absent.

Fails open: any backend error degrades to "no cache / no cap" rather than
raising, so search never breaks because the cache is unavailable.
"""
from __future__ import annotations

import json
import logging
import os
import time

log = logging.getLogger(__name__)

_redis = None
_redis_tried = False

# in-process fallbacks
_mem_kv: dict[str, tuple[float, str]] = {}   # key -> (expiry_epoch, json_value)
_mem_ctr: dict[str, int] = {}                # counter key -> count


def _client():
    global _redis, _redis_tried
    if _redis_tried:
        return _redis
    _redis_tried = True
    url = os.environ.get("REDIS_URL", "")
    if not url:
        return None
    try:
        import redis  # type: ignore
        _redis = redis.from_url(url, socket_timeout=2, decode_responses=True)
        _redis.ping()
    except Exception as e:
        log.warning("apify cache: Redis unavailable (%s) — using in-process fallback", e)
        _redis = None
    return _redis


def get_json(key: str):
    r = _client()
    if r is not None:
        try:
            raw = r.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            log.warning("apify cache get failed: %s", e)
            return None
    entry = _mem_kv.get(key)
    if not entry:
        return None
    expiry, raw = entry
    if expiry < time.time():
        _mem_kv.pop(key, None)
        return None
    return json.loads(raw)


def set_json(key: str, value, ttl_secs: int) -> None:
    raw = json.dumps(value)
    r = _client()
    if r is not None:
        try:
            r.setex(key, ttl_secs, raw)
            return
        except Exception as e:
            log.warning("apify cache set failed: %s", e)
            return
    _mem_kv[key] = (time.time() + ttl_secs, raw)


def incr_daily(counter: str, ttl_secs: int = 90000) -> int:
    """Increment a per-day counter and return the new value. ttl defaults to
    ~25h so the key self-expires."""
    r = _client()
    if r is not None:
        try:
            n = r.incr(counter)
            if n == 1:
                r.expire(counter, ttl_secs)
            return int(n)
        except Exception as e:
            log.warning("apify cost counter failed: %s", e)
            return 0  # fail open — do not cap when counter is broken
    _mem_ctr[counter] = _mem_ctr.get(counter, 0) + 1
    return _mem_ctr[counter]
