"""Generic Apify actor runner — shared by linkedin, facebook, instagram handlers.

Uses Apify's synchronous run-and-get-dataset-items endpoint (no client-side poll
loop), with shared result caching and a daily cost cap so repeated/scheduled
searches don't re-run paid actors. All controls are env-driven:

    APIFY_API_TOKEN        — required; without it the runner returns [] (no-op)
    APIFY_CACHE_TTL        — seconds to cache identical runs (default 21600 = 6h)
    APIFY_MAX_RUNS_PER_DAY — cost cap; beyond it the runner returns [] (default 200)
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone

import requests

from aiplatform.skills.research.sources import _cache

log = logging.getLogger(__name__)

_APIFY_BASE = "https://api.apify.com/v2"
_DEFAULT_CACHE_TTL = 21600       # 6 hours
_DEFAULT_MAX_RUNS_PER_DAY = 200


def _cache_key(actor_id: str, run_input: dict) -> str:
    blob = actor_id + "|" + json.dumps(run_input, sort_keys=True, default=str)
    return "apify:items:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _over_cost_cap() -> bool:
    try:
        cap = int(os.environ.get("APIFY_MAX_RUNS_PER_DAY", _DEFAULT_MAX_RUNS_PER_DAY))
    except (TypeError, ValueError):
        cap = _DEFAULT_MAX_RUNS_PER_DAY
    if cap <= 0:
        return False  # cap disabled
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    count = _cache.incr_daily(f"apify:runs:{day}")
    if count > cap:
        log.warning("Apify daily run cap reached (%d/%d) — skipping run", count, cap)
        return True
    return False


def run_actor(actor_id: str, run_input: dict, timeout_secs: int = 120) -> list[dict]:
    """
    Run an Apify actor and return its dataset items.

    Cached: identical (actor_id, run_input) pairs reuse a recent result for
    APIFY_CACHE_TTL seconds. Cost-capped: beyond APIFY_MAX_RUNS_PER_DAY runs/day
    the runner returns []. Falls back to [] (not a hard failure) on any error or
    a missing token — callers must handle empty results gracefully.
    """
    token = os.environ.get("APIFY_API_TOKEN", "")
    if not token:
        log.warning("APIFY_API_TOKEN not set — skipping actor %s", actor_id)
        return []

    key = _cache_key(actor_id, run_input)
    cached = _cache.get_json(key)
    if cached is not None:
        log.info("Apify cache hit for %s (%d items)", actor_id, len(cached))
        return cached

    if _over_cost_cap():
        return []

    try:
        ttl = int(os.environ.get("APIFY_CACHE_TTL", _DEFAULT_CACHE_TTL))
    except (TypeError, ValueError):
        ttl = _DEFAULT_CACHE_TTL

    try:
        # Synchronous run — Apify blocks server-side and returns dataset items in
        # one response (no client poll loop). `timeout` bounds the run server-side.
        resp = requests.post(
            f"{_APIFY_BASE}/acts/{actor_id}/run-sync-get-dataset-items",
            params={"token": token, "timeout": timeout_secs, "format": "json", "limit": 100},
            json=run_input,
            timeout=timeout_secs + 30,
        )
        if resp.status_code not in (200, 201):
            log.warning("Apify run failed for %s: HTTP %s", actor_id, resp.status_code)
            return []
        items = resp.json()
        if not isinstance(items, list):
            return []
        _cache.set_json(key, items, ttl)
        return items
    except Exception as e:
        log.warning("Apify actor %s error: %s", actor_id, e)
        return []
