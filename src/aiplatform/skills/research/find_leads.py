"""
Skill: find_leads
Search for potential customers across open channels for each venture.

Channels per venture:
  marketing_audit    — Reddit (r/smallbusiness, r/entrepreneur, r/startups),
                       SerpAPI web search ("site:reddit.com need marketing help"),
                       Hacker News (news.ycombinator.com/ask)
  content_studio     — Reddit (r/podcasting, r/podcast),
                       Castbox/Listen Notes new shows (web search),
                       SerpAPI ("new podcast launched 2026 show notes")
  accessibility_audit — Reddit (r/webdev, r/web_design, r/accessibility),
                        SerpAPI ("website accessibility audit needed"),
                        ProductHunt (new launches missing accessibility)

Returns a list of lead dicts ready to be persisted to the leads table.
Each lead: {venture, source_channel, source_url, name, email, website_url, company, notes}
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

# ── Channel config per venture ─────────────────────────────────────────────────

VENTURE_CHANNELS: dict[str, list[dict]] = {
    "marketing_audit": [
        {
            "channel": "reddit",
            "subreddits": ["smallbusiness", "entrepreneur", "startups", "digital_marketing"],
            "keywords": ["website help", "marketing audit", "website feedback", "seo help",
                         "website not converting", "website traffic", "marketing strategy"],
        },
        {
            "channel": "web_search",
            "queries": [
                "site:reddit.com \"my website\" \"need help\" marketing -job",
                "site:reddit.com \"website audit\" OR \"seo audit\" smallbusiness",
                "\"looking for\" \"website audit\" OR \"marketing audit\" freelancer",
            ],
        },
        {
            "channel": "hackernews",
            "queries": ["marketing", "website", "landing page", "seo"],
            "post_type": "ask",
        },
    ],
    "content_studio": [
        {
            "channel": "reddit",
            "subreddits": ["podcasting", "podcast", "podcasters", "startpodcasting"],
            "keywords": ["show notes", "new podcast", "just launched", "podcast help",
                         "podcast editing", "podcast marketing", "episode description"],
        },
        {
            "channel": "web_search",
            "queries": [
                "site:reddit.com podcasting \"show notes\" help OR struggling",
                "new podcast launched 2026 \"show notes\" service",
                "\"podcast show notes\" service freelancer site:reddit.com",
            ],
        },
        {
            "channel": "listennotes",
            "queries": ["new podcast 2026"],
        },
    ],
    "accessibility_audit": [
        {
            "channel": "reddit",
            "subreddits": ["webdev", "web_design", "accessibility", "frontend", "wordpress"],
            "keywords": ["wcag", "accessibility", "ada compliance", "screen reader",
                         "website accessibility", "axe", "lighthouse accessibility"],
        },
        {
            "channel": "web_search",
            "queries": [
                "site:reddit.com \"accessibility\" \"website\" help OR audit webdev",
                "\"wcag compliance\" OR \"ada compliance\" website audit freelancer",
                "site:producthunt.com accessibility -tool 2026",
            ],
        },
    ],
}

# ── Reddit search (no API key needed for public search) ───────────────────────

_REDDIT_HEADERS = {
    "User-Agent": "EchoForge-LeadBot/1.0 (by /u/echoforge_bot)",
    "Accept": "application/json",
}

def _search_reddit(subreddit: str, query: str, limit: int = 10) -> list[dict]:
    """Search a subreddit for posts matching a keyword."""
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {"q": query, "sort": "new", "t": "month", "limit": limit, "restrict_sr": 1}
    try:
        resp = requests.get(url, headers=_REDDIT_HEADERS, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        posts = resp.json().get("data", {}).get("children", [])
        results = []
        for post in posts:
            d = post.get("data", {})
            if d.get("is_self") and len(d.get("selftext", "")) > 50:
                results.append({
                    "title": d.get("title", ""),
                    "text": d.get("selftext", "")[:500],
                    "author": d.get("author", ""),
                    "url": f"https://www.reddit.com{d.get('permalink', '')}",
                    "subreddit": subreddit,
                    "score": d.get("score", 0),
                })
        return results
    except Exception as e:
        log.warning("Reddit search failed for r/%s q=%s: %s", subreddit, query, e)
        return []


def _reddit_user_profile_url(username: str) -> str:
    return f"https://www.reddit.com/user/{username}"


# ── SerpAPI web search ─────────────────────────────────────────────────────────

def _serpapi_search(query: str, num: int = 5) -> list[dict]:
    """Search Google via SerpAPI."""
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        log.warning("SERPAPI_KEY not set — skipping web search")
        return []
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={"engine": "google", "q": query, "num": num, "api_key": api_key},
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        results = resp.json().get("organic_results", [])
        return [{"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")}
                for r in results]
    except Exception as e:
        log.warning("SerpAPI search failed for '%s': %s", query, e)
        return []


# ── Listen Notes (podcast discovery) ──────────────────────────────────────────

def _search_listennotes(query: str, limit: int = 10) -> list[dict]:
    """Search Listen Notes for new podcasts (free tier)."""
    api_key = os.environ.get("LISTENNOTES_API_KEY", "")
    headers = {"X-ListenAPI-Key": api_key} if api_key else {}
    try:
        resp = requests.get(
            "https://listen-api.listennotes.com/api/v2/search",
            params={"q": query, "type": "podcast", "sort_by_date": 1, "len_min": 1},
            headers=headers,
            timeout=15,
        )
        if resp.status_code not in (200, 201):
            return []
        results = resp.json().get("results", [])
        return [
            {
                "title": r.get("title_original", ""),
                "website": r.get("website", "") or r.get("listennotes_url", ""),
                "email": r.get("email", ""),
                "description": (r.get("description_original", "") or "")[:300],
            }
            for r in results[:limit]
        ]
    except Exception as e:
        log.warning("Listen Notes search failed: %s", e)
        return []


# ── Claude-powered lead extraction ────────────────────────────────────────────

def _extract_lead_context(post: dict, venture: str) -> dict | None:
    """
    Use Claude to decide if a Reddit post represents a real lead and extract context.
    Returns a lead dict or None if not a good fit.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    venture_pitch = {
        "marketing_audit": "a website marketing audit service that scores websites on SEO, messaging, conversion, and competitive positioning",
        "content_studio": "a podcast show notes service that turns audio episodes into professional show notes, transcripts, and social content",
        "accessibility_audit": "a WCAG accessibility audit service that scans websites for accessibility violations",
    }.get(venture, "a digital service")

    prompt = f"""You are screening Reddit posts to find potential customers for {venture_pitch}.

Post title: {post.get('title', '')}
Post text: {post.get('text', '')}
Author: {post.get('author', '')}
URL: {post.get('url', '')}

Is this person a potential customer? Reply with JSON only:
{{
  "is_lead": true/false,
  "confidence": "high/medium/low",
  "name": "their Reddit username or real name if mentioned",
  "website_url": "their website URL if mentioned, else null",
  "company": "company name if mentioned, else null",
  "notes": "1-2 sentence summary of why they're a good fit and what their specific pain is"
}}

Only mark is_lead=true if there's a genuine problem or need that matches the service. Be selective."""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        text = msg.content[0].text.strip()
        # Strip markdown code fences if present
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        if not data.get("is_lead"):
            return None
        return {
            "name": data.get("name") or post.get("author", ""),
            "website_url": data.get("website_url"),
            "company": data.get("company"),
            "notes": data.get("notes", ""),
            "confidence": data.get("confidence", "medium"),
        }
    except Exception as e:
        log.warning("Lead extraction Claude call failed: %s", e)
        return None


# ── Main entry point ───────────────────────────────────────────────────────────

def find_leads(
    venture: str,
    max_leads: int = 20,
    channels: list[str] | None = None,
) -> list[dict]:
    """
    Search for potential customers for a given venture across configured channels.

    Args:
        venture:   One of marketing_audit, content_studio, accessibility_audit
        max_leads: Cap on leads returned (to control API costs)
        channels:  Optional subset of channels to use (reddit, web_search, listennotes)

    Returns:
        List of lead dicts ready for DB insertion:
        {venture, source_channel, source_url, name, email, website_url, company, notes}
    """
    if venture not in VENTURE_CHANNELS:
        raise ValueError(f"Unknown venture '{venture}'. Valid: {list(VENTURE_CHANNELS)}")

    config = VENTURE_CHANNELS[venture]
    raw_posts: list[tuple[str, dict]] = []  # (source_channel, post_dict)

    for channel_cfg in config:
        ch = channel_cfg["channel"]
        if channels and ch not in channels:
            continue

        if ch == "reddit":
            for subreddit in channel_cfg.get("subreddits", []):
                for keyword in channel_cfg.get("keywords", [])[:3]:  # limit API calls
                    posts = _search_reddit(subreddit, keyword, limit=5)
                    for p in posts:
                        raw_posts.append((ch, p))
                    time.sleep(0.5)  # Reddit rate limit

        elif ch == "web_search":
            for query in channel_cfg.get("queries", []):
                results = _serpapi_search(query, num=5)
                for r in results:
                    raw_posts.append((ch, {
                        "title": r["title"],
                        "text": r["snippet"],
                        "url": r["url"],
                        "author": "",
                    }))

        elif ch == "listennotes":
            for query in channel_cfg.get("queries", []):
                shows = _search_listennotes(query, limit=10)
                for show in shows:
                    raw_posts.append((ch, {
                        "title": show["title"],
                        "text": show["description"],
                        "url": show["website"],
                        "author": "",
                        "email": show.get("email", ""),
                    }))

    log.info("find_leads: %d raw candidates for '%s'", len(raw_posts), venture)

    leads = []
    seen_urls: set[str] = set()

    for source_channel, post in raw_posts:
        if len(leads) >= max_leads:
            break

        url = post.get("url", "")
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # For Listen Notes results, skip Claude extraction (already structured)
        if source_channel == "listennotes":
            if post.get("email") or post.get("url"):
                leads.append({
                    "venture": venture,
                    "source_channel": source_channel,
                    "source_url": url,
                    "name": post.get("author", ""),
                    "email": post.get("email", "") or None,
                    "website_url": url or None,
                    "company": None,
                    "notes": post.get("text", "")[:300],
                    "status": "new",
                })
            continue

        # Use Claude to qualify the lead
        extracted = _extract_lead_context(post, venture)
        if not extracted:
            continue

        leads.append({
            "venture": venture,
            "source_channel": source_channel,
            "source_url": url,
            "name": extracted.get("name") or "",
            "email": None,  # Reddit doesn't expose emails
            "website_url": extracted.get("website_url"),
            "company": extracted.get("company"),
            "notes": extracted.get("notes", ""),
            "status": "new",
        })

    log.info("find_leads: %d qualified leads found for '%s'", len(leads), venture)
    return leads
