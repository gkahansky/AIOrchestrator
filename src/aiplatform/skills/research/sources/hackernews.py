"""Hacker News via Algolia API — free, no key required."""
import logging

import requests

from aiplatform.skills.research.sources.base import RawPost

log = logging.getLogger(__name__)


def search(keywords: list[str], config: dict) -> list[RawPost]:
    """
    config keys:
        post_type: "ask" | "show" | "story"  (default: "ask")
        limit:     int                         (default: 10)
    """
    tag_map = {"ask": "ask_hn", "show": "show_hn", "story": "story"}
    post_type = config.get("post_type", "ask")
    tag = tag_map.get(post_type, "ask_hn")
    limit = int(config.get("limit", 10))

    results: list[RawPost] = []
    seen: set[str] = set()

    for kw in keywords[:4]:
        try:
            resp = requests.get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": kw, "tags": tag, "hitsPerPage": limit},
                timeout=10,
            )
            if resp.status_code != 200:
                continue
            for h in resp.json().get("hits", []):
                text = (h.get("story_text") or h.get("comment_text") or "")[:800]
                if len(text) < 30:
                    continue
                url = f"https://news.ycombinator.com/item?id={h.get('objectID', '')}"
                if url in seen:
                    continue
                seen.add(url)
                results.append(RawPost(
                    title=h.get("title", ""),
                    text=text,
                    author=h.get("author", ""),
                    url=url,
                    source_channel="hackernews",
                ))
        except Exception as e:
            log.warning("HN Algolia '%s': %s", kw, e)

    return results
