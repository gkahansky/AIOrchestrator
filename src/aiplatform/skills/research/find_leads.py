"""
Skill: find_leads
Search for potential customers across multiple channels per venture.

Channels:
  reddit        — Public subreddit search (no API key needed)
  google        — Broad buying-intent Google searches via SerpAPI
  linkedin      — Public LinkedIn posts via Google site: filter (SerpAPI)
  hackernews    — Algolia HN API — Ask HN and Show HN posts (no key needed)
  indiehackers  — IndieHackers posts via SerpAPI (no key needed beyond SerpAPI)
  fiverr        — Fiverr buyer requests via session cookie scrape;
                  falls back to Google signals if FIVERR_SESSION_COOKIE not set
  listennotes   — Listen Notes podcast discovery API (content_studio only)

Required env vars:
  ANTHROPIC_API_KEY     — Claude Haiku for lead qualification
  SERPAPI_KEY           — Google/LinkedIn/IndieHackers/Fiverr signal searches
  LISTENNOTES_API_KEY   — Optional; Listen Notes free tier (content_studio)
  FIVERR_SESSION_COOKIE — Optional; Fiverr buyer requests (sellers only)

Returns list of lead dicts ready for DB insertion.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

# ── Channel config per venture ─────────────────────────────────────────────────
# Each entry names a channel and its search parameters.
# All channels are attempted in order; results are pooled and Claude-qualified.

VENTURE_CHANNELS: dict[str, list[dict]] = {
    "marketing_audit": [
        {
            "channel": "reddit",
            "subreddits": ["smallbusiness", "entrepreneur", "startups", "digital_marketing", "SEO", "ecommerce"],
            "keywords": [
                "website not converting", "website help", "marketing audit",
                "website feedback", "seo help", "website traffic",
                "marketing strategy", "website redesign", "landing page help",
            ],
        },
        {
            "channel": "google",
            "queries": [
                "\"need help with\" \"website\" OR \"marketing\" site:reddit.com OR site:indiehackers.com",
                "\"looking for\" \"marketing consultant\" OR \"website audit\" freelancer 2025 OR 2026",
                "\"my website\" \"not converting\" OR \"no traffic\" OR \"bounce rate\" help",
                "\"website audit\" OR \"marketing audit\" \"anyone recommend\" -fiverr",
            ],
        },
        {
            "channel": "linkedin",
            "queries": [
                "website not converting looking for marketing help",
                "small business marketing struggles website traffic",
                "looking for website feedback conversion rate",
            ],
        },
        {
            "channel": "hackernews",
            "queries": ["marketing website landing page seo", "website conversion startup"],
            "post_type": "ask",
        },
        {
            "channel": "indiehackers",
            "queries": [
                "website not converting marketing help",
                "looking for marketing audit feedback website",
            ],
        },
        {
            "channel": "fiverr",
            "queries": ["marketing audit", "website audit seo", "website feedback conversion"],
        },
    ],

    "content_studio": [
        {
            "channel": "reddit",
            "subreddits": ["podcasting", "podcast", "podcasters", "startpodcasting", "entrepreneur"],
            "keywords": [
                "show notes", "new podcast", "just launched my podcast", "podcast help",
                "podcast editing", "podcast marketing", "episode description",
                "transcript", "podcast growth",
            ],
        },
        {
            "channel": "google",
            "queries": [
                "\"new podcast\" \"show notes\" help OR service 2025 OR 2026",
                "\"podcast show notes\" \"looking for\" OR \"anyone recommend\" service",
                "\"started a podcast\" \"show notes\" OR \"transcript\" help",
                "site:reddit.com podcasting \"show notes\" struggling OR need help",
            ],
        },
        {
            "channel": "linkedin",
            "queries": [
                "just launched my podcast looking for show notes help",
                "podcast content creator looking for transcript show notes service",
                "new podcast episode content repurposing",
            ],
        },
        {
            "channel": "hackernews",
            "queries": ["podcast show notes transcript automation", "podcast content creation"],
            "post_type": "ask",
        },
        {
            "channel": "indiehackers",
            "queries": [
                "podcast show notes help service",
                "new podcast launched content",
            ],
        },
        {
            "channel": "fiverr",
            "queries": ["podcast show notes", "podcast transcript", "podcast content"],
        },
        {
            "channel": "listennotes",
            "queries": ["new podcast 2026", "new podcast 2025"],
        },
    ],

    "accessibility_audit": [
        {
            "channel": "reddit",
            "subreddits": ["webdev", "web_design", "accessibility", "frontend", "wordpress", "startups"],
            "keywords": [
                "wcag", "accessibility audit", "ada compliance", "screen reader",
                "website accessibility", "axe results", "lighthouse accessibility",
                "accessibility issues", "508 compliance",
            ],
        },
        {
            "channel": "google",
            "queries": [
                "\"website accessibility\" \"looking for\" audit OR help 2025 OR 2026",
                "\"ada compliance\" \"website\" need help OR audit freelancer",
                "\"wcag\" \"website\" issues OR violations fix help",
                "site:reddit.com webdev accessibility audit OR compliance help",
            ],
        },
        {
            "channel": "linkedin",
            "queries": [
                "website accessibility compliance audit looking for help",
                "ada wcag website compliance small business",
                "web accessibility remediation looking for expert",
            ],
        },
        {
            "channel": "hackernews",
            "queries": ["website accessibility wcag ada compliance", "accessibility audit web"],
            "post_type": "ask",
        },
        {
            "channel": "indiehackers",
            "queries": [
                "website accessibility compliance audit",
                "ada compliance website startup",
            ],
        },
        {
            "channel": "fiverr",
            "queries": ["accessibility audit wcag", "ada compliance website", "website accessibility"],
        },
    ],
}

# ── Reddit ─────────────────────────────────────────────────────────────────────

_REDDIT_HEADERS = {
    "User-Agent": "EchoForge-LeadBot/1.0 (research tool)",
    "Accept": "application/json",
}

def _search_reddit(subreddit: str, query: str, limit: int = 8) -> list[dict]:
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
                    "text": d.get("selftext", "")[:600],
                    "author": d.get("author", ""),
                    "url": f"https://www.reddit.com{d.get('permalink', '')}",
                    "subreddit": subreddit,
                    "score": d.get("score", 0),
                })
        return results
    except Exception as e:
        log.warning("Reddit search failed r/%s q=%s: %s", subreddit, query, e)
        return []


# ── Google via SerpAPI ─────────────────────────────────────────────────────────

def _serpapi_google(query: str, num: int = 5) -> list[dict]:
    """Generic Google search via SerpAPI. Used by google, linkedin, indiehackers channels."""
    api_key = os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        log.warning("SERPAPI_KEY not set — skipping: %s", query[:60])
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
        results = resp.json().get("organic_results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("link", ""),
                "text": r.get("snippet", ""),
                "author": "",
            }
            for r in results
        ]
    except Exception as e:
        log.warning("SerpAPI error for '%s': %s", query[:60], e)
        return []


def _search_linkedin(query: str, num: int = 5) -> list[dict]:
    """
    Find public LinkedIn posts via Google site: search.
    LinkedIn's own API is too restricted for post discovery without an approved partner app.
    Google indexes most public LinkedIn posts within a few days.
    """
    google_query = f'site:linkedin.com/posts OR site:linkedin.com/pulse {query}'
    results = _serpapi_google(google_query, num=num)
    # Tag them as linkedin source for the lead record
    for r in results:
        r["source"] = "linkedin"
    return results


def _search_indiehackers(query: str, num: int = 5) -> list[dict]:
    google_query = f'site:indiehackers.com {query}'
    return _serpapi_google(google_query, num=num)


# ── Hacker News via Algolia (no API key needed) ────────────────────────────────

def _search_hackernews(query: str, post_type: str = "ask", limit: int = 10) -> list[dict]:
    """
    Search HN via the Algolia API. Free, no key required, up to 1000 req/hour.
    post_type: 'ask' (Ask HN), 'show' (Show HN), or 'story' (any post)
    """
    tag_map = {"ask": "ask_hn", "show": "show_hn", "story": "story"}
    tag = tag_map.get(post_type, "ask_hn")
    try:
        resp = requests.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": query, "tags": tag, "hitsPerPage": limit},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        hits = resp.json().get("hits", [])
        results = []
        for h in hits:
            text = (h.get("story_text") or h.get("comment_text") or "")[:500]
            if len(text) < 30:
                continue
            results.append({
                "title": h.get("title", ""),
                "text": text,
                "author": h.get("author", ""),
                "url": f"https://news.ycombinator.com/item?id={h.get('objectID', '')}",
            })
        return results
    except Exception as e:
        log.warning("HN Algolia search failed for '%s': %s", query, e)
        return []


# ── Fiverr buyer requests ──────────────────────────────────────────────────────

_FIVERR_BUYER_REQUESTS_URL = "https://www.fiverr.com/requests/pending"

def _search_fiverr_buyer_requests(queries: list[str]) -> list[dict]:
    """
    Fetch Fiverr buyer requests using a seller session cookie.
    Requires FIVERR_SESSION_COOKIE env var (copy from browser DevTools → Application → Cookies
    while logged into your Fiverr seller account, value of the cookie named 'SL_G_WPT_TO' and
    'XSRF-TOKEN' — or the simplest approach: the full Cookie header string).

    Falls back to Google signals if the cookie is not set.
    """
    session_cookie = os.environ.get("FIVERR_SESSION_COOKIE", "")

    if not session_cookie:
        # Fallback: search Google for Fiverr buying intent signals
        results = []
        for q in queries[:2]:
            google_results = _serpapi_google(
                f'site:fiverr.com/requests {q} OR "I need" {q}', num=3
            )
            results.extend(google_results)
        log.info("Fiverr: no session cookie — used Google fallback (%d results)", len(results))
        return results

    # Direct Fiverr buyer requests scrape
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": session_cookie,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.fiverr.com",
    }
    try:
        resp = requests.get(
            "https://www.fiverr.com/requests/pending",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 401 or resp.status_code == 403:
            log.warning("Fiverr: session cookie rejected (HTTP %s) — falling back to Google", resp.status_code)
            return _search_fiverr_buyer_requests.__wrapped__(queries)  # type: ignore[attr-defined]

        # Fiverr returns HTML with embedded JSON. Look for the buyer requests block.
        text = resp.text
        # Find __BUYER_REQUESTS__ or similar embedded JSON
        match = re.search(r'"buyer_requests"\s*:\s*(\[.*?\])', text, re.DOTALL)
        if not match:
            # Try alternate pattern used in some Fiverr page layouts
            match = re.search(r'window\.__DATA__\s*=\s*(\{.*?\});', text, re.DOTALL)
            if not match:
                log.warning("Fiverr: could not parse buyer requests from page")
                return []
            data = json.loads(match.group(1))
            requests_list = data.get("buyerRequests", data.get("buyer_requests", []))
        else:
            requests_list = json.loads(match.group(1))

        results = []
        for req in requests_list[:20]:
            title = req.get("title", "") or req.get("description", "")[:80]
            desc = req.get("description", "") or req.get("body", "")
            budget = req.get("budget", {})
            budget_str = f" Budget: ${budget.get('min', '')}-${budget.get('max', '')}" if budget else ""
            results.append({
                "title": title,
                "text": f"{desc}{budget_str}"[:500],
                "author": req.get("buyer", {}).get("username", "") if isinstance(req.get("buyer"), dict) else "",
                "url": "https://www.fiverr.com/requests/pending",
            })
        log.info("Fiverr: found %d buyer requests", len(results))
        return results

    except Exception as e:
        log.warning("Fiverr buyer request scrape failed: %s", e)
        return []

# Unwrapped reference for fallback recursion guard
_search_fiverr_buyer_requests.__wrapped__ = lambda queries: []  # type: ignore[attr-defined]


# ── Listen Notes ───────────────────────────────────────────────────────────────

def _search_listennotes(query: str, limit: int = 10) -> list[dict]:
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


# ── Claude lead qualification ──────────────────────────────────────────────────

def _extract_lead_context(post: dict, venture: str, search_prompt: str | None = None) -> dict | None:
    """
    Use Claude Haiku to decide if a post is a real lead and extract structured context.
    Returns a lead dict or None if not a good fit.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    venture_pitch = {
        "marketing_audit": "a website marketing audit service (SEO, messaging, conversion, competitive positioning)",
        "content_studio": "a podcast show notes service (audio → show notes, transcripts, social content)",
        "accessibility_audit": "a WCAG accessibility audit service (violation scan, prioritised fix list with code examples)",
    }.get(venture, "a digital service")

    criteria_block = (
        f"\nCAMPAIGN SEARCH CRITERIA (user-approved — apply these when qualifying):\n{search_prompt}\n"
        if search_prompt else ""
    )

    prompt = f"""You are screening a post to find potential customers for {venture_pitch}.
{criteria_block}
Source: {post.get('source_channel', 'web')}
Title: {post.get('title', '')}
Text: {post.get('text', '')}
Author: {post.get('author', '')}
URL: {post.get('url', '')}

Is this person a potential customer who would benefit from this service?
Reply with JSON only — no explanation outside the JSON:
{{
  "is_lead": true or false,
  "confidence": "high" | "medium" | "low",
  "name": "real name or username if visible, else null",
  "website_url": "their website URL if mentioned, else null",
  "company": "company or project name if visible, else null",
  "notes": "1-2 sentences: why they're a good fit and what their specific pain point is"
}}

Be selective. Only mark is_lead=true if there is a clear, genuine need that matches the service."""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        if not data.get("is_lead"):
            return None
        return {
            "name":       data.get("name") or post.get("author", ""),
            "website_url": data.get("website_url"),
            "company":    data.get("company"),
            "notes":      data.get("notes", ""),
            "confidence": data.get("confidence", "medium"),
        }
    except Exception as e:
        log.warning("Claude lead extraction failed: %s", e)
        return None


# ── Main entry point ───────────────────────────────────────────────────────────

def find_leads(
    venture: str,
    max_leads: int = 20,
    channels: list[str] | None = None,
    search_prompt: str | None = None,
) -> list[dict]:
    """
    Search for potential customers across all configured channels for a venture.

    Args:
        venture:       marketing_audit | content_studio | accessibility_audit
        max_leads:     Max leads to return (controls Claude API cost)
        channels:      Optional subset — None means all channels
        search_prompt: User-reviewed criteria prompt injected into Claude qualification

    Returns:
        List of lead dicts ready for DB insertion.
    """
    if venture not in VENTURE_CHANNELS:
        raise ValueError(f"Unknown venture '{venture}'. Valid: {list(VENTURE_CHANNELS)}")

    config = VENTURE_CHANNELS[venture]
    # (source_channel, post_dict) — post_dict must have: title, text, url, author
    raw_posts: list[tuple[str, dict]] = []

    for channel_cfg in config:
        ch = channel_cfg["channel"]
        if channels and ch not in channels:
            continue

        log.info("find_leads: searching channel '%s' for '%s'", ch, venture)

        if ch == "reddit":
            for subreddit in channel_cfg.get("subreddits", []):
                for keyword in channel_cfg.get("keywords", [])[:3]:
                    for p in _search_reddit(subreddit, keyword, limit=5):
                        p["source_channel"] = "reddit"
                        raw_posts.append(("reddit", p))
                    time.sleep(0.5)  # Reddit public API rate limit

        elif ch == "google":
            for query in channel_cfg.get("queries", []):
                for r in _serpapi_google(query, num=5):
                    r["source_channel"] = "google"
                    raw_posts.append(("google", r))

        elif ch == "linkedin":
            for query in channel_cfg.get("queries", []):
                for r in _search_linkedin(query, num=5):
                    r["source_channel"] = "linkedin"
                    raw_posts.append(("linkedin", r))

        elif ch == "hackernews":
            post_type = channel_cfg.get("post_type", "ask")
            for query in channel_cfg.get("queries", []):
                for p in _search_hackernews(query, post_type=post_type, limit=8):
                    p["source_channel"] = "hackernews"
                    raw_posts.append(("hackernews", p))

        elif ch == "indiehackers":
            for query in channel_cfg.get("queries", []):
                for r in _search_indiehackers(query, num=5):
                    r["source_channel"] = "indiehackers"
                    raw_posts.append(("indiehackers", r))

        elif ch == "fiverr":
            queries = channel_cfg.get("queries", [])
            for p in _search_fiverr_buyer_requests(queries):
                p["source_channel"] = "fiverr"
                raw_posts.append(("fiverr", p))

        elif ch == "listennotes":
            for query in channel_cfg.get("queries", []):
                for show in _search_listennotes(query, limit=10):
                    raw_posts.append(("listennotes", {
                        "source_channel": "listennotes",
                        "title": show["title"],
                        "text": show["description"],
                        "url": show["website"],
                        "author": "",
                        "email": show.get("email", ""),
                        "website_url": show["website"],
                    }))

    log.info("find_leads: %d raw candidates across all channels for '%s'", len(raw_posts), venture)

    leads: list[dict] = []
    seen_urls: set[str] = set()

    for source_channel, post in raw_posts:
        if len(leads) >= max_leads:
            break

        url = post.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        # Listen Notes: already structured, skip Claude
        if source_channel == "listennotes":
            if post.get("email") or post.get("url"):
                leads.append({
                    "venture":        venture,
                    "source_channel": "listennotes",
                    "source_url":     url or None,
                    "name":           post.get("author") or None,
                    "email":          post.get("email") or None,
                    "website_url":    post.get("website_url") or url or None,
                    "company":        None,
                    "notes":          post.get("text", "")[:300],
                    "status":         "new",
                })
            continue

        # All other channels: Claude qualification
        extracted = _extract_lead_context(post, venture, search_prompt)
        if not extracted:
            continue

        leads.append({
            "venture":        venture,
            "source_channel": source_channel,
            "source_url":     url or None,
            "name":           extracted.get("name") or None,
            "email":          post.get("email") or None,  # Fiverr/LN may have emails
            "website_url":    extracted.get("website_url"),
            "company":        extracted.get("company"),
            "notes":          extracted.get("notes", ""),
            "status":         "new",
        })

    log.info("find_leads: %d qualified leads for '%s' (from %d candidates)", len(leads), venture, len(raw_posts))
    return leads
