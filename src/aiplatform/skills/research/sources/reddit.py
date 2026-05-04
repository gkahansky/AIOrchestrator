"""Reddit source handler — public JSON API, no key required."""
import logging
import time

import requests

from aiplatform.skills.research.sources.base import RawPost

log = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "EchoForge-LeadBot/1.0 (research tool)", "Accept": "application/json"}


def search(keywords: list[str], config: dict) -> list[RawPost]:
    """
    Search one or more subreddits for posts matching the given keywords.

    config keys:
        subreddits: list[str]   — subreddits to search (default: ["entrepreneur"])
        limit:      int         — results per subreddit/keyword pair (default: 5)
        sort:       str         — "new" | "relevance" (default: "new")
        time_filter: str        — "month" | "week" | "year" (default: "month")
    """
    subreddits = config.get("subreddits") or ["entrepreneur"]
    limit = int(config.get("limit", 5))
    sort = config.get("sort", "new")
    time_filter = config.get("time_filter", "month")

    results: list[RawPost] = []
    seen: set[str] = set()

    for subreddit in subreddits:
        for keyword in keywords[:4]:  # cap per source to avoid excessive API calls
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
            params = {"q": keyword, "sort": sort, "t": time_filter,
                      "limit": limit, "restrict_sr": 1}
            try:
                resp = requests.get(url, headers=_HEADERS, params=params, timeout=10)
                if resp.status_code != 200:
                    continue
                for post in resp.json().get("data", {}).get("children", []):
                    d = post.get("data", {})
                    post_url = f"https://www.reddit.com{d.get('permalink', '')}"
                    if post_url in seen:
                        continue
                    body = d.get("selftext", "")
                    if not d.get("is_self") or len(body) < 50:
                        continue
                    seen.add(post_url)
                    results.append(RawPost(
                        title=d.get("title", ""),
                        text=body[:1000],
                        author=d.get("author", ""),
                        url=post_url,
                        source_channel="reddit",
                    ))
            except Exception as e:
                log.warning("Reddit r/%s kw=%s: %s", subreddit, keyword, e)
            time.sleep(0.5)

    return results
