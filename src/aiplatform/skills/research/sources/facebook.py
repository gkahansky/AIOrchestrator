"""
Facebook Groups source handler.

Primary: Apify Facebook Groups Scraper (apify/facebook-groups-scraper).
Fallback: Google site:facebook.com/groups search via SerpAPI.

When no `group_urls` are configured, candidate groups are discovered from a
Google `site:facebook.com/groups` search. With `include_comments`, post comments
are mined too (intent often lives in the comments). A native provider can be
wired via sources.providers.resolve_provider without touching this handler.

config keys:
    group_urls:       list[str]  — specific Facebook group URLs to scrape
    max_posts:        int        — posts per group (default: 20)
    include_comments: bool       — also mine post comments (default: False)
    recency_days, geo, language, min_engagement, max_results — relevance filters
"""
import logging

from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources.google import serpapi_search
from aiplatform.skills.research.sources import apify as apify_runner
from aiplatform.skills.research.sources import _provider
from aiplatform.skills.research.sources._filters import apply_filters
from aiplatform.skills.research.sources.query_builder import filters_from_config

log = logging.getLogger(__name__)

_APIFY_ACTOR = "apify/facebook-groups-scraper"
_APIFY_COMMENTS_ACTOR = "apify/facebook-comments-scraper"


def _engagement(item: dict) -> int:
    def _n(*keys):
        for k in keys:
            v = item.get(k)
            if isinstance(v, (int, float)):
                return int(v)
        return 0
    return _n("likesCount", "reactionsCount", "likes") + _n("commentsCount", "comments")


def _group_url(link: str) -> str:
    """Normalise any facebook group link to the group landing URL."""
    if "/groups/" not in link:
        return ""
    gid = link.split("/groups/", 1)[1].strip("/").split("/")[0].split("?")[0]
    return f"https://www.facebook.com/groups/{gid}" if gid else ""


def _discover_group_urls(keywords: list[str], limit: int = 5) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for kw in keywords[:3]:
        for post in serpapi_search(f"site:facebook.com/groups {kw}", num=5):
            g = _group_url(post.url)
            if g and g not in seen:
                seen.add(g)
                found.append(g)
                if len(found) >= limit:
                    return found
    return found


def _post_to_rawpost(item: dict) -> RawPost | None:
    text = item.get("text") or item.get("message") or ""
    if len(text) < 30:
        return None
    user = item.get("user") if isinstance(item.get("user"), dict) else {}
    author = item.get("authorName") or user.get("name", "")
    author_url = item.get("authorProfileUrl") or user.get("profileUrl") or user.get("url") or ""
    return RawPost(
        title=text[:80],
        text=text[:1000],
        author=author,
        url=item.get("url") or item.get("postUrl", ""),
        author_url=author_url,
        author_handle=str(item.get("authorId") or user.get("id") or ""),
        posted_at=(item.get("time") or item.get("timestamp") or ""),
        engagement=_engagement(item),
        source_channel="facebook",
    )


def _mine_comments(post_urls: list[str], max_posts: int = 5) -> list[RawPost]:
    results: list[RawPost] = []
    for url in [u for u in post_urls if u][:max_posts]:
        items = apify_runner.run_actor(_APIFY_COMMENTS_ACTOR, {"startUrls": [{"url": url}]})
        for item in items:
            text = item.get("text") or item.get("commentText") or ""
            if len(text) < 30:
                continue
            user = item.get("user") if isinstance(item.get("user"), dict) else {}
            results.append(RawPost(
                title=text[:80],
                text=text[:1000],
                author=item.get("authorName") or user.get("name", ""),
                url=url,
                author_url=item.get("profileUrl") or user.get("profileUrl") or "",
                author_handle=str(item.get("authorId") or user.get("id") or ""),
                posted_at=(item.get("date") or ""),
                source_channel="facebook",
            ))
    return results


def _search_via_apify(keywords: list[str], group_urls: list[str],
                      max_posts: int, include_comments: bool) -> list[RawPost]:
    results: list[RawPost] = []
    seen: set[str] = set()
    post_urls: list[str] = []

    for group_url in group_urls[:5]:
        items = apify_runner.run_actor(_APIFY_ACTOR, {
            "startUrls": [{"url": group_url}],
            "maxPosts": max_posts,
            "searchTerms": keywords[:4],
        })
        for item in items:
            rp = _post_to_rawpost(item)
            if rp and rp.url not in seen:
                seen.add(rp.url)
                results.append(rp)
                post_urls.append(rp.url)

    if include_comments and post_urls:
        results.extend(_mine_comments(post_urls))
    return results


def _search_via_google(keywords: list[str], group_urls: list[str], num: int = 5) -> list[RawPost]:
    results: list[RawPost] = []
    seen: set[str] = set()

    sites = []
    for u in group_urls[:3]:
        clean = u.rstrip("/").replace("https://", "").replace("http://", "www.")
        sites.append(f"site:{clean}")
    if not sites:
        sites = ["site:facebook.com/groups"]

    for kw in keywords[:3]:
        for site in sites[:2]:
            for post in serpapi_search(f"{site} {kw}", num=num):
                if post.url not in seen:
                    seen.add(post.url)
                    post.source_channel = "facebook"
                    results.append(post)
    return results


def _default_search(keywords: list[str], config: dict) -> list[RawPost]:
    import os
    group_urls: list[str] = config.get("group_urls") or []
    max_posts = int(config.get("max_posts", 20))
    include_comments = bool(config.get("include_comments", False))
    has_apify = bool(os.environ.get("APIFY_API_TOKEN", ""))

    # Discover groups when none configured so the source works out of the box.
    if not group_urls:
        group_urls = _discover_group_urls(keywords)

    results: list[RawPost] = []
    if has_apify and group_urls:
        results = _search_via_apify(keywords, group_urls, max_posts, include_comments)
    if not results:
        results = _search_via_google(keywords, group_urls)
    return apply_filters(results, filters_from_config(config))


def search(keywords: list[str], config: dict) -> list[RawPost]:
    return _provider.run(keywords, config, "facebook", _default_search)
