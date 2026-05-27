"""
Relevance filtering applied to RawPosts before the paid Claude qualifier.

Drops stale and low-engagement posts so they never cost a Haiku call. Fails
open: a post with no `posted_at`/`engagement` data is kept (we never had the
signal, so we don't penalise it).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources.query_builder import Filters

log = logging.getLogger(__name__)


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        # tolerate trailing Z
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _is_stale(post: RawPost, recency_days: int, now: datetime) -> bool:
    dt = _parse_iso(post.posted_at)
    if dt is None:
        return False  # unknown age — keep
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).days > recency_days


def apply_filters(posts: list[RawPost], filters: Filters) -> list[RawPost]:
    now = datetime.now(timezone.utc)
    out: list[RawPost] = []
    for p in posts:
        if filters.recency_days and _is_stale(p, filters.recency_days, now):
            continue
        if filters.min_engagement and p.engagement and p.engagement < filters.min_engagement:
            continue
        out.append(p)
        if filters.max_results and len(out) >= filters.max_results:
            break
    dropped = len(posts) - len(out)
    if dropped:
        log.info("source filters: kept %d, dropped %d", len(out), dropped)
    return out
