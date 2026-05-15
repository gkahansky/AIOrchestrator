"""
YouTube source handler.

Searches for YouTube videos matching keywords, then fetches top comments
from each video as lead signals. Comments expressing pain points around
content repurposing, time constraints, or editing burden are strong leads.

Requires: YOUTUBE_API_KEY env var (YouTube Data API v3).
Free quota: 10,000 units/day. Each search = 100 units; each comments fetch = 1 unit.

config keys:
    max_videos:            int — videos to search (default: 5)
    max_comments_per_video: int — top comments per video (default: 10)
"""
import logging
import os

import requests

from aiplatform.skills.research.sources.base import RawPost

log = logging.getLogger(__name__)

_YT_BASE = "https://www.googleapis.com/youtube/v3"


def _search_videos(keywords: list[str], api_key: str, max_videos: int) -> list[dict]:
    """Return a list of {video_id, title, channel_title} for keyword-matched videos."""
    results: list[dict] = []
    seen: set[str] = set()

    for kw in keywords[:4]:
        try:
            resp = requests.get(
                f"{_YT_BASE}/search",
                params={
                    "part": "snippet",
                    "q": kw,
                    "type": "video",
                    "maxResults": max_videos,
                    "order": "relevance",
                    "key": api_key,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                log.warning("YouTube search failed for '%s': HTTP %s", kw, resp.status_code)
                continue
            for item in resp.json().get("items", []):
                vid_id = item.get("id", {}).get("videoId", "")
                if vid_id and vid_id not in seen:
                    seen.add(vid_id)
                    results.append({
                        "video_id": vid_id,
                        "title": item["snippet"].get("title", ""),
                        "channel": item["snippet"].get("channelTitle", ""),
                    })
        except Exception as e:
            log.warning("YouTube search error for '%s': %s", kw, e)

    return results


def _fetch_comments(video: dict, api_key: str, max_comments: int) -> list[RawPost]:
    """Fetch top-level comments for a video and map to RawPost."""
    posts: list[RawPost] = []
    vid_id = video["video_id"]
    vid_url = f"https://www.youtube.com/watch?v={vid_id}"

    try:
        resp = requests.get(
            f"{_YT_BASE}/commentThreads",
            params={
                "part": "snippet",
                "videoId": vid_id,
                "maxResults": max_comments,
                "order": "relevance",
                "key": api_key,
            },
            timeout=15,
        )
        if resp.status_code == 403:
            # Comments disabled on this video — skip silently
            return []
        if resp.status_code != 200:
            log.warning("YouTube comments failed for video %s: HTTP %s", vid_id, resp.status_code)
            return []

        for item in resp.json().get("items", []):
            top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            text = top.get("textDisplay") or top.get("textOriginal", "")
            author = top.get("authorDisplayName", "")
            author_url = top.get("authorChannelUrl", "")
            if len(text) < 30:
                continue
            posts.append(RawPost(
                title=video["title"],
                text=text[:1000],
                author=author,
                url=vid_url,
                website_url=author_url or None,
                source_channel="youtube",
            ))
    except Exception as e:
        log.warning("YouTube comments error for video %s: %s", vid_id, e)

    return posts


def search(keywords: list[str], config: dict) -> list[RawPost]:
    """
    Search YouTube comments for lead signals.

    config keys:
        max_videos:            int (default: 5)
        max_comments_per_video: int (default: 10)
    """
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        log.warning("YOUTUBE_API_KEY not set — skipping YouTube source")
        return []

    max_videos = int(config.get("max_videos", 5))
    max_comments = int(config.get("max_comments_per_video", 10))

    videos = _search_videos(keywords, api_key, max_videos)
    if not videos:
        return []

    results: list[RawPost] = []
    seen_authors: set[str] = set()

    for video in videos:
        for post in _fetch_comments(video, api_key, max_comments):
            # One post per unique author (avoid flooding from same commenter)
            key = f"{post.author}:{post.url}"
            if key not in seen_authors:
                seen_authors.add(key)
                results.append(post)

    log.info("youtube: %d comment posts from %d videos", len(results), len(videos))
    return results
