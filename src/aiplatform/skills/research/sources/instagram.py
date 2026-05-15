"""
Instagram source handler.

Primary:  Apify instagram-hashtag-scraper — searches hashtags for posts whose
          captions signal content-creation pain points.
Fallback: Google site:instagram.com search via SerpAPI.

config keys:
    hashtags:  list[str] — Instagram hashtags to scrape (without #)
               e.g. ["fitnesscontent", "contentcreator", "videoediting"]
    max_posts: int       — posts per hashtag (default: 15, Apify)
"""
import logging
import os

from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources.google import serpapi_search
from aiplatform.skills.research.sources import apify as apify_runner

log = logging.getLogger(__name__)

_APIFY_ACTOR = "apify/instagram-hashtag-scraper"


def _search_via_apify(hashtags: list[str], keywords: list[str], max_posts: int) -> list[RawPost]:
    results: list[RawPost] = []
    seen: set[str] = set()

    for hashtag in hashtags[:5]:
        run_input = {
            "hashtags": [hashtag.lstrip("#")],
            "resultsLimit": max_posts,
        }
        items = apify_runner.run_actor(_APIFY_ACTOR, run_input)
        for item in items:
            caption = item.get("caption") or item.get("text") or ""
            owner = (
                item.get("ownerUsername")
                or item.get("username")
                or item.get("owner", {}).get("username", "")
            )
            shortcode = item.get("shortCode") or item.get("id", "")
            url = (
                item.get("url")
                or (f"https://www.instagram.com/p/{shortcode}/" if shortcode else "")
            )
            profile_url = f"https://www.instagram.com/{owner}/" if owner else ""

            if len(caption) < 30 or url in seen:
                continue
            seen.add(url)
            results.append(RawPost(
                title=caption[:80],
                text=caption[:1000],
                author=owner,
                url=url,
                website_url=profile_url or None,
                source_channel="instagram",
            ))

    return results


def _search_via_google(keywords: list[str], hashtags: list[str], num: int = 5) -> list[RawPost]:
    results: list[RawPost] = []
    seen: set[str] = set()

    # Build search terms from hashtags + keywords
    terms = [f"#{h}" for h in hashtags[:3]] + keywords[:3]

    for term in terms[:4]:
        query = f"site:instagram.com {term}"
        for post in serpapi_search(query, num=num):
            if post.url not in seen:
                seen.add(post.url)
                post.source_channel = "instagram"
                results.append(post)

    return results


def search(keywords: list[str], config: dict) -> list[RawPost]:
    hashtags: list[str] = config.get("hashtags") or []
    max_posts = int(config.get("max_posts", 15))
    has_apify = bool(os.environ.get("APIFY_API_TOKEN", ""))

    if has_apify and hashtags:
        results = _search_via_apify(hashtags, keywords, max_posts)
        if results:
            return results

    # Fallback — Google signal search
    return _search_via_google(keywords, hashtags)
