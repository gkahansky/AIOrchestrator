"""
Skill: find_leads
Search for potential customers across configured sources and qualify them with Claude.

Entry point:
    find_leads(sources, max_leads, search_prompt, personas) -> list[dict]

Each source is a dict matching the CampaignSource model:
    {platform, name, keywords, config, enabled}

If no sources are provided, falls back to VENTURE_DEFAULT_SOURCES[venture].

Required env vars:
    ANTHROPIC_API_KEY     — Claude Haiku for lead qualification
    SERPAPI_KEY           — Google / LinkedIn / IndieHackers / Fiverr signal searches
    APIFY_API_TOKEN       — Optional; Apify actors for LinkedIn + Facebook Groups
    LISTENNOTES_API_KEY   — Optional; Listen Notes podcast discovery
    FIVERR_SESSION_COOKIE — Optional; Fiverr buyer requests scrape
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from aiplatform.skills.research.sources import HANDLERS

log = logging.getLogger(__name__)


def _load_outreach_config() -> dict:
    config_path = Path(
        os.environ.get("OUTREACH_CONFIG_PATH", "config/outreach_sources.json")
    )
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}

_cfg = _load_outreach_config()


# ── Default sources per venture ────────────────────────────────────────────────
# Loaded from config/outreach_sources.json (OUTREACH_CONFIG_PATH to override).
# Edit the JSON file to add/change sources without a code deploy.

VENTURE_DEFAULT_SOURCES: dict[str, list[dict]] = _cfg.get("default_sources", {
    "marketing_audit": [
        {
            "platform": "reddit",
            "name": "Marketing subreddits",
            "keywords": [
                "website not converting", "seo help", "website traffic",
                "marketing strategy", "website redesign", "landing page help",
            ],
            "config": {"subreddits": ["smallbusiness", "entrepreneur", "startups",
                                      "digital_marketing", "SEO", "ecommerce"]},
        },
        {
            "platform": "google",
            "name": "Google — buying intent",
            "keywords": [
                "\"need help with\" \"website\" OR \"marketing\" site:reddit.com OR site:indiehackers.com",
                "\"looking for\" \"marketing consultant\" OR \"website audit\" freelancer 2025 OR 2026",
                "\"my website\" \"not converting\" OR \"no traffic\" OR \"bounce rate\" help",
            ],
            "config": {},
        },
        {
            "platform": "linkedin",
            "name": "LinkedIn posts",
            "keywords": [
                "website not converting looking for marketing help",
                "small business marketing struggles website traffic",
            ],
            "config": {},
        },
        {
            "platform": "hackernews",
            "name": "Hacker News Ask HN",
            "keywords": ["marketing website landing page seo", "website conversion startup"],
            "config": {"post_type": "ask"},
        },
        {
            "platform": "indiehackers",
            "name": "IndieHackers",
            "keywords": ["website not converting marketing help", "looking for marketing audit"],
            "config": {},
        },
        {
            "platform": "fiverr",
            "name": "Fiverr buyer requests",
            "keywords": ["marketing audit", "website audit seo", "website feedback conversion"],
            "config": {},
        },
    ],

    "content_studio": [
        {
            "platform": "reddit",
            "name": "Podcasting subreddits",
            "keywords": [
                "show notes", "new podcast", "podcast help",
                "podcast editing", "transcript", "podcast growth",
            ],
            "config": {"subreddits": ["podcasting", "podcast", "podcasters",
                                      "startpodcasting", "entrepreneur"]},
        },
        {
            "platform": "google",
            "name": "Google — podcast searches",
            "keywords": [
                "\"new podcast\" \"show notes\" help OR service 2025 OR 2026",
                "\"podcast show notes\" \"looking for\" OR \"anyone recommend\" service",
                "site:reddit.com podcasting \"show notes\" struggling OR need help",
            ],
            "config": {},
        },
        {
            "platform": "linkedin",
            "name": "LinkedIn — podcast creators",
            "keywords": [
                "just launched my podcast looking for show notes help",
                "new podcast episode content repurposing",
            ],
            "config": {},
        },
        {
            "platform": "hackernews",
            "name": "Hacker News",
            "keywords": ["podcast show notes transcript automation"],
            "config": {"post_type": "ask"},
        },
        {
            "platform": "fiverr",
            "name": "Fiverr buyer requests",
            "keywords": ["podcast show notes", "podcast transcript", "podcast content"],
            "config": {},
        },
        {
            "platform": "listennotes",
            "name": "Listen Notes — new podcasts",
            "keywords": ["new podcast 2026", "new podcast 2025"],
            "config": {},
        },
    ],

    "accessibility_audit": [
        {
            "platform": "reddit",
            "name": "Web dev subreddits",
            "keywords": [
                "wcag", "accessibility audit", "ada compliance",
                "website accessibility", "accessibility issues", "508 compliance",
            ],
            "config": {"subreddits": ["webdev", "web_design", "accessibility",
                                      "frontend", "wordpress", "startups"]},
        },
        {
            "platform": "google",
            "name": "Google — accessibility searches",
            "keywords": [
                "\"website accessibility\" \"looking for\" audit OR help 2025 OR 2026",
                "\"ada compliance\" \"website\" need help OR audit freelancer",
                "\"wcag\" \"website\" issues OR violations fix help",
            ],
            "config": {},
        },
        {
            "platform": "linkedin",
            "name": "LinkedIn — accessibility",
            "keywords": [
                "website accessibility compliance audit looking for help",
                "ada wcag website compliance small business",
            ],
            "config": {},
        },
        {
            "platform": "hackernews",
            "name": "Hacker News",
            "keywords": ["website accessibility wcag ada compliance"],
            "config": {"post_type": "ask"},
        },
        {
            "platform": "fiverr",
            "name": "Fiverr buyer requests",
            "keywords": ["accessibility audit wcag", "ada compliance website"],
            "config": {},
        },
    ],
})

_VENTURE_PITCHES: dict[str, str] = _cfg.get("venture_pitches", {
    "marketing_audit":    "a website marketing audit service (SEO, messaging, conversion, competitive positioning)",
    "content_studio":     "a podcast show notes service (audio → show notes, transcripts, social content)",
    "accessibility_audit":"a WCAG accessibility audit service (violation scan, prioritised fix list with code examples)",
    "security_audit":     "a web application security audit service (vulnerability scan, OWASP Top 10, pentest-style report with prioritised findings and code-level fix recommendations)",
    "market_research":    "a market research service (AI-powered competitive analysis, TAM estimates, customer segment breakdown, go-to-market strategy — delivered as a structured PDF report)",
})


# ── Mock leads (test mode) ─────────────────────────────────────────────────────

def _load_mock_leads(venture: str) -> list[dict]:
    """Return fixture leads for the given venture from config/test_leads.json."""
    config_path = Path(
        os.environ.get("TEST_LEADS_PATH", "config/test_leads.json")
    )
    if not config_path.exists():
        log.warning("_load_mock_leads: %s not found — returning empty list", config_path)
        return []
    all_leads: dict = json.loads(config_path.read_text())
    fixtures = all_leads.get(venture, [])
    results = []
    for f in fixtures:
        results.append({
            "venture": venture,
            "source_channel": f.get("source_channel", "mock"),
            "source_url": f.get("source_url"),
            "name": f.get("name"),
            "email": f.get("email"),
            "platform_username": f.get("platform_username"),
            "website_url": f.get("website_url"),
            "company": f.get("company"),
            "notes": f.get("notes"),
            "context": f.get("context"),
            "matched_persona": f.get("matched_persona"),
        })
    log.info("_load_mock_leads: returning %d fixture leads for '%s'", len(results), venture)
    return results


# ── Claude qualification ───────────────────────────────────────────────────────

def _qualify_post(
    post_dict: dict,
    venture: str,
    search_prompt: str | None,
    personas: list[dict] | None,
) -> dict | None:
    """
    Ask Claude Haiku whether a raw post is a genuine lead.
    Returns a lead-enrichment dict or None if not a good fit.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    venture_pitch = _VENTURE_PITCHES.get(venture, "a digital service")

    persona_block = ""
    if personas:
        lines = "\n".join(f"  - {p.get('name','')}: {p.get('description','')}" for p in personas)
        persona_block = f"\nCUSTOMER PERSONAS (use these to qualify and match):\n{lines}\n"

    criteria_block = (
        f"\nCAMPAIGN SEARCH CRITERIA:\n{search_prompt}\n" if search_prompt else ""
    )

    prompt = f"""You are screening a post to find potential customers for {venture_pitch}.
{persona_block}{criteria_block}
Source: {post_dict.get('source_channel', 'web')}
Title: {post_dict.get('title', '')}
Text: {post_dict.get('text', '')}
Author: {post_dict.get('author', '')}
URL: {post_dict.get('url', '')}

Is this person a potential customer who would benefit from this service?
Reply with JSON only:
{{
  "is_lead": true or false,
  "confidence": "high" | "medium" | "low",
  "name": "real name or username if visible, else null",
  "website_url": "their website URL if mentioned, else null",
  "company": "company or project name if visible, else null",
  "matched_persona": "name of the best matching persona from the list, or null",
  "notes": "1-2 sentences: why they're a good fit and what their specific pain point is"
}}

Be selective. Only mark is_lead=true if there is a clear, genuine need."""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if not data.get("is_lead"):
            return None
        return {
            "name":            data.get("name") or post_dict.get("author", ""),
            "website_url":     data.get("website_url"),
            "company":         data.get("company"),
            "matched_persona": data.get("matched_persona"),
            "notes":           data.get("notes", ""),
            "confidence":      data.get("confidence", "medium"),
        }
    except Exception as e:
        log.warning("Claude qualification failed: %s", e)
        return None


# ── Main entry point ───────────────────────────────────────────────────────────

def find_leads(
    sources: list[dict],
    max_leads: int = 20,
    search_prompt: str | None = None,
    personas: list[dict] | None = None,
    venture: str = "",
    mock_mode: bool = False,
) -> list[dict]:
    """
    Search configured sources for potential customers.

    Args:
        sources:       List of source dicts {platform, name, keywords, config, enabled}.
                       Falls back to VENTURE_DEFAULT_SOURCES[venture] if empty.
        max_leads:     Max qualified leads to return (controls Claude API cost).
        search_prompt: User-reviewed criteria injected into Claude qualification.
        personas:      Campaign personas [{name, description}] for matching.
        venture:       Venture slug — used only for default-source fallback.
        mock_mode:     When True, return fixture leads from config/test_leads.json
                       instead of hitting real platforms. No API calls are made.

    Returns:
        List of lead dicts ready for DB insertion (includes `context` field).
    """
    if mock_mode:
        return _load_mock_leads(venture)

    active_sources = [s for s in sources if s.get("enabled", True)]

    if not active_sources and venture in VENTURE_DEFAULT_SOURCES:
        active_sources = VENTURE_DEFAULT_SOURCES[venture]
        log.info("find_leads: no sources configured — using defaults for '%s'", venture)

    raw_posts: list[dict] = []

    for src in active_sources:
        platform = src.get("platform", "")
        handler = HANDLERS.get(platform)
        if not handler:
            log.warning("find_leads: unknown platform '%s' — skipping", platform)
            continue

        keywords = src.get("keywords") or []
        config = src.get("config") or {}
        log.info("find_leads: searching '%s' (%s)", src.get("name", platform), platform)

        try:
            posts = handler.search(keywords, config)
            for p in posts:
                raw_posts.append({
                    "title":          p.title,
                    "text":           p.text,
                    "author":         p.author,
                    "url":            p.url,
                    "email":          p.email,
                    "website_url":    p.website_url,
                    "source_channel": p.source_channel or platform,
                })
        except Exception as e:
            log.warning("find_leads: handler '%s' error: %s", platform, e)

    log.info("find_leads: %d raw candidates across all sources", len(raw_posts))

    leads: list[dict] = []
    seen_urls: set[str] = set()

    for post in raw_posts:
        if len(leads) >= max_leads:
            break

        url = post.get("url", "")
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)

        # Listen Notes: already structured, skip Claude qualification
        if post.get("source_channel") == "listennotes":
            if post.get("email") or post.get("url"):
                leads.append({
                    "venture":         venture,
                    "source_channel":  "listennotes",
                    "source_url":      url or None,
                    "name":            post.get("author") or None,
                    "email":           post.get("email") or None,
                    "website_url":     post.get("website_url") or url or None,
                    "company":         None,
                    "notes":           post.get("text", "")[:300],
                    "context":         post.get("text", "")[:1000],
                    "matched_persona": None,
                    "status":          "new",
                })
            continue

        extracted = _qualify_post(post, venture, search_prompt, personas)
        if not extracted:
            continue

        leads.append({
            "venture":         venture,
            "source_channel":  post.get("source_channel", "web"),
            "source_url":      url or None,
            "name":            extracted.get("name") or None,
            "email":           post.get("email") or None,
            "platform_username": (
                post.get("author") if post.get("source_channel") in
                ("reddit", "fiverr", "linkedin", "facebook", "instagram") else None
            ),
            "website_url":     extracted.get("website_url"),
            "company":         extracted.get("company"),
            "notes":           extracted.get("notes", ""),
            "context":         post.get("text", "")[:2000],   # preserve raw post for personalized reply
            "matched_persona": extracted.get("matched_persona"),
            "status":          "new",
        })

    log.info("find_leads: %d qualified leads (from %d candidates)", len(leads), len(raw_posts))
    return leads
