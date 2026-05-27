"""
LinkedIn source handler.

Primary: Apify LinkedIn Posts Scraper (apify/linkedin-post-search-scraper).
Fallback: Google site:linkedin.com search via SerpAPI (no additional key needed).

A native people-search provider (e.g. Unipile) can be wired via
sources.providers.resolve_provider without touching this handler.

config keys:
    recency_days, geo, language, min_engagement, max_results — relevance filters
"""
import logging

from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources.google import serpapi_search
from aiplatform.skills.research.sources import apify as apify_runner
from aiplatform.skills.research.sources import _provider
from aiplatform.skills.research.sources._filters import apply_filters
from aiplatform.skills.research.sources.query_builder import (
    boolean_query, filters_from_config,
)

log = logging.getLogger(__name__)

_APIFY_ACTOR = "apify/linkedin-post-search-scraper"


def _profile_slug(url: str) -> str:
    """Extract the /in/{slug} handle from a LinkedIn profile URL."""
    if not url or "/in/" not in url:
        return ""
    return url.split("/in/", 1)[1].strip("/").split("/")[0].split("?")[0]


def _engagement(item: dict) -> int:
    def _n(*keys):
        for k in keys:
            v = item.get(k)
            if isinstance(v, (int, float)):
                return int(v)
        return 0
    return _n("numLikes", "likesCount", "reactions") + _n("numComments", "commentsCount")


def _search_via_apify(keywords: list[str]) -> list[RawPost]:
    results: list[RawPost] = []
    query = boolean_query(keywords[:6]) or " ".join(keywords[:4])
    items = apify_runner.run_actor(_APIFY_ACTOR, {"searchQuery": query, "maxResults": 25})
    for item in items:
        text = item.get("text") or item.get("commentary") or ""
        author_obj = item.get("author") if isinstance(item.get("author"), dict) else {}
        author = item.get("authorName") or author_obj.get("fullName", "")
        url = item.get("url") or item.get("postUrl", "")
        author_url = (
            item.get("authorProfileUrl") or item.get("authorUrl")
            or author_obj.get("url") or author_obj.get("profileUrl") or ""
        )
        if len(text) < 30:
            continue
        results.append(RawPost(
            title=text[:80],
            text=text[:1000],
            author=author,
            url=url,
            author_url=author_url,
            author_handle=_profile_slug(author_url),
            author_headline=(item.get("authorHeadline") or author_obj.get("occupation") or ""),
            posted_at=(item.get("postedAtISO") or item.get("postedAt") or ""),
            engagement=_engagement(item),
            source_channel="linkedin",
        ))
    return results


def _search_via_google(keywords: list[str], num: int = 5) -> list[RawPost]:
    results: list[RawPost] = []
    seen: set[str] = set()
    for kw in keywords[:4]:
        query = f'site:linkedin.com/posts OR site:linkedin.com/pulse {kw}'
        for post in serpapi_search(query, num=num):
            if post.url not in seen:
                seen.add(post.url)
                post.source_channel = "linkedin"
                results.append(post)
    return results


def _default_search(keywords: list[str], config: dict) -> list[RawPost]:
    import os
    has_apify = bool(os.environ.get("APIFY_API_TOKEN", ""))
    results: list[RawPost] = []
    if has_apify:
        results = _search_via_apify(keywords)
    if not results:
        results = _search_via_google(keywords)
    return apply_filters(results, filters_from_config(config))


def search(keywords: list[str], config: dict) -> list[RawPost]:
    return _provider.run(keywords, config, "linkedin", _default_search)
