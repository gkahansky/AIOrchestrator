"""
Facebook Groups source handler — NEW.

Primary: Apify Facebook Groups Scraper (apify/facebook-groups-scraper).
Fallback: Google site:facebook.com/groups search via SerpAPI.

config keys:
    group_urls: list[str]  — specific Facebook group URLs to scrape
                             e.g. ["https://www.facebook.com/groups/smallbizowners"]
    max_posts:  int        — posts per group (default: 20, Apify)
"""
import logging
import os

from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources.google import serpapi_search
from aiplatform.skills.research.sources import apify as apify_runner

log = logging.getLogger(__name__)

_APIFY_ACTOR = "apify/facebook-groups-scraper"


def _search_via_apify(keywords: list[str], group_urls: list[str], max_posts: int) -> list[RawPost]:
    results: list[RawPost] = []
    seen: set[str] = set()

    for group_url in group_urls[:5]:
        run_input = {
            "startUrls": [{"url": group_url}],
            "maxPosts": max_posts,
            "searchTerms": keywords[:4],
        }
        items = apify_runner.run_actor(_APIFY_ACTOR, run_input)
        for item in items:
            text = item.get("text") or item.get("message") or ""
            author = item.get("authorName") or item.get("user", {}).get("name", "")
            url = item.get("url") or item.get("postUrl", "")
            if len(text) < 30 or url in seen:
                continue
            seen.add(url)
            results.append(RawPost(
                title=text[:80],
                text=text[:1000],
                author=author,
                url=url,
                source_channel="facebook",
            ))
    return results


def _search_via_google(keywords: list[str], group_urls: list[str], num: int = 5) -> list[RawPost]:
    results: list[RawPost] = []
    seen: set[str] = set()

    # Use specific group URLs as site filters when available
    sites = []
    for u in group_urls[:3]:
        # e.g. "https://www.facebook.com/groups/abc" → "site:facebook.com/groups/abc"
        clean = u.rstrip("/").replace("https://", "").replace("http://", "www.")
        sites.append(f"site:{clean}")

    if not sites:
        sites = ["site:facebook.com/groups"]

    for kw in keywords[:3]:
        for site in sites[:2]:
            query = f'{site} {kw}'
            for post in serpapi_search(query, num=num):
                if post.url not in seen:
                    seen.add(post.url)
                    post.source_channel = "facebook"
                    results.append(post)
    return results


def search(keywords: list[str], config: dict) -> list[RawPost]:
    group_urls: list[str] = config.get("group_urls") or []
    max_posts = int(config.get("max_posts", 20))
    has_apify = bool(os.environ.get("APIFY_API_TOKEN", ""))

    if has_apify and group_urls:
        results = _search_via_apify(keywords, group_urls, max_posts)
        if results:
            return results

    # Fallback — Google signal search
    return _search_via_google(keywords, group_urls)
