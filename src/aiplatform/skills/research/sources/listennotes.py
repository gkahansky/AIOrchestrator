"""Listen Notes podcast discovery — content_studio leads."""
import logging
import os

import requests

from aiplatform.skills.research.sources.base import RawPost

log = logging.getLogger(__name__)


def search(keywords: list[str], config: dict) -> list[RawPost]:
    """
    config keys:
        limit: int — results per query (default: 10)
    """
    api_key = os.environ.get("LISTENNOTES_API_KEY", "")
    headers = {"X-ListenAPI-Key": api_key} if api_key else {}
    limit = int(config.get("limit", 10))
    results: list[RawPost] = []
    seen: set[str] = set()

    for kw in keywords[:3]:
        try:
            resp = requests.get(
                "https://listen-api.listennotes.com/api/v2/search",
                params={"q": kw, "type": "podcast", "sort_by_date": 1, "len_min": 1},
                headers=headers,
                timeout=15,
            )
            if resp.status_code not in (200, 201):
                continue
            for r in resp.json().get("results", [])[:limit]:
                website = r.get("website", "") or r.get("listennotes_url", "")
                if website in seen:
                    continue
                seen.add(website)
                results.append(RawPost(
                    title=r.get("title_original", ""),
                    text=(r.get("description_original", "") or "")[:600],
                    url=website,
                    email=r.get("email", ""),
                    website_url=website,
                    source_channel="listennotes",
                ))
        except Exception as e:
            log.warning("Listen Notes '%s': %s", kw, e)

    return results
