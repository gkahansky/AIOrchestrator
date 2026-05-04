"""Google search via SerpAPI — used directly and as fallback by other handlers."""
import logging
import os

import requests

from aiplatform.skills.research.sources.base import RawPost

log = logging.getLogger(__name__)


def serpapi_search(query: str, num: int = 5) -> list[RawPost]:
    """Generic SerpAPI Google search. Used by google, linkedin, indiehackers, facebook handlers."""
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        log.warning("SERPAPI_KEY not set — skipping query: %s", query[:60])
        return []
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": query, "num": num, "api_key": api_key},
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning("SerpAPI HTTP %s for: %s", resp.status_code, query[:60])
            return []
        return [
            RawPost(
                title=r.get("title", ""),
                text=r.get("snippet", ""),
                url=r.get("link", ""),
                source_channel="google",
            )
            for r in resp.json().get("organic_results", [])
        ]
    except Exception as e:
        log.warning("SerpAPI error '%s': %s", query[:60], e)
        return []


def search(keywords: list[str], config: dict) -> list[RawPost]:
    """
    Google search via SerpAPI.

    Each keyword is used as a search query directly.
    config keys:
        num_results: int — results per query (default: 5)
        site_filter: str — e.g. "site:reddit.com" prepended to each query
    """
    num = int(config.get("num_results", 5))
    site = config.get("site_filter", "")
    results: list[RawPost] = []
    seen: set[str] = set()

    for kw in keywords[:6]:
        query = f"{site} {kw}".strip() if site else kw
        for post in serpapi_search(query, num=num):
            if post.url not in seen:
                seen.add(post.url)
                results.append(post)

    return results
