"""
LinkedIn source handler.

Primary: Apify LinkedIn Posts Scraper (apify/linkedin-post-search-scraper).
Fallback: Google site:linkedin.com search via SerpAPI (no additional key needed).

config keys:
    use_apify: bool — force Apify even if token present (default: auto-detect)
"""
import logging
import os

from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources.google import serpapi_search
from aiplatform.skills.research.sources import apify as apify_runner

log = logging.getLogger(__name__)

_APIFY_ACTOR = "apify/linkedin-post-search-scraper"


def _search_via_apify(keywords: list[str]) -> list[RawPost]:
    results: list[RawPost] = []
    for kw in keywords[:4]:
        items = apify_runner.run_actor(_APIFY_ACTOR, {"searchQuery": kw, "maxResults": 10})
        for item in items:
            text = item.get("text") or item.get("commentary") or ""
            author = item.get("authorName") or item.get("author", {}).get("fullName", "")
            url = item.get("url") or item.get("postUrl", "")
            if len(text) < 30:
                continue
            results.append(RawPost(
                title=text[:80],
                text=text[:1000],
                author=author,
                url=url,
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


def search(keywords: list[str], config: dict) -> list[RawPost]:
    has_apify = bool(os.environ.get("APIFY_API_TOKEN", ""))
    if has_apify:
        results = _search_via_apify(keywords)
        if results:
            return results
    return _search_via_google(keywords)
