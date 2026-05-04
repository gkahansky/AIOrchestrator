"""IndieHackers via Google site: search (SerpAPI)."""
import logging

from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources.google import serpapi_search

log = logging.getLogger(__name__)


def search(keywords: list[str], config: dict) -> list[RawPost]:
    """
    config keys:
        num_results: int (default: 5)
    """
    num = int(config.get("num_results", 5))
    results: list[RawPost] = []
    seen: set[str] = set()

    for kw in keywords[:4]:
        for post in serpapi_search(f"site:indiehackers.com {kw}", num=num):
            if post.url not in seen:
                seen.add(post.url)
                post.source_channel = "indiehackers"
                results.append(post)

    return results
