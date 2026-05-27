"""
Query + relevance-filter helpers shared by source handlers.

Venture-agnostic: turns a source's `keywords` + `config` filter knobs into
platform-appropriate queries, and exposes a `Filters` value object the handlers
apply (via `_filters.apply_filters`) before the paid Claude qualification step.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Filters:
    recency_days: int | None = None   # drop posts older than N days (needs posted_at)
    geo: str = ""                     # ISO country/region hint (e.g. "US")
    language: str = ""                # ISO language hint (e.g. "en")
    min_engagement: int = 0           # drop posts below this reaction+comment count
    max_results: int | None = None    # cap results returned by a handler


def filters_from_config(config: dict) -> Filters:
    """Parse the standard relevance knobs from a source's config dict."""
    def _int(key):
        v = config.get(key)
        try:
            return int(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    return Filters(
        recency_days=_int("recency_days"),
        geo=str(config.get("geo") or ""),
        language=str(config.get("language") or ""),
        min_engagement=_int("min_engagement") or 0,
        max_results=_int("max_results"),
    )


def boolean_query(keywords: list[str]) -> str:
    """Combine keywords into a single OR-boolean query string. Multi-word
    keywords are quoted so they match as phrases."""
    terms = []
    for kw in keywords:
        kw = (kw or "").strip()
        if not kw:
            continue
        terms.append(f'"{kw}"' if " " in kw and not kw.startswith('"') else kw)
    return " OR ".join(terms)


def google_site_query(site: str, keyword: str, recency_days: int | None = None) -> str:
    """Build a `site:` Google query. Recency is applied via SerpAPI `tbs` by the
    caller; this only assembles the textual query."""
    parts = []
    if site:
        parts.append(site if site.startswith("site:") else f"site:{site}")
    if keyword:
        parts.append(keyword)
    return " ".join(parts).strip()
