"""
Fiverr buyer requests handler.

Primary: session-cookie scrape of the buyer requests page.
Fallback: Google site:fiverr.com signals via SerpAPI.

config keys:
    (none — relies on FIVERR_SESSION_COOKIE env var)
"""
import json
import logging
import os
import re

import requests

from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources.google import serpapi_search

log = logging.getLogger(__name__)


def _scrape_buyer_requests(keywords: list[str]) -> list[RawPost]:
    session_cookie = os.environ.get("FIVERR_SESSION_COOKIE", "")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": session_cookie,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.fiverr.com",
    }
    try:
        resp = requests.get("https://www.fiverr.com/requests/pending", headers=headers, timeout=15)
        if resp.status_code in (401, 403):
            log.warning("Fiverr: session cookie rejected (HTTP %s)", resp.status_code)
            return []

        text = resp.text
        match = re.search(r'"buyer_requests"\s*:\s*(\[.*?\])', text, re.DOTALL)
        if not match:
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
            author = req.get("buyer", {}).get("username", "") if isinstance(req.get("buyer"), dict) else ""
            results.append(RawPost(
                title=title,
                text=f"{desc}{budget_str}"[:800],
                author=author,
                url="https://www.fiverr.com/requests/pending",
                source_channel="fiverr",
            ))
        return results
    except Exception as e:
        log.warning("Fiverr scrape failed: %s", e)
        return []


def _fallback_google(keywords: list[str]) -> list[RawPost]:
    results: list[RawPost] = []
    seen: set[str] = set()
    for kw in keywords[:2]:
        for post in serpapi_search(f'site:fiverr.com/requests {kw} OR "I need" {kw}', num=3):
            if post.url not in seen:
                seen.add(post.url)
                post.source_channel = "fiverr"
                results.append(post)
    return results


def search(keywords: list[str], config: dict) -> list[RawPost]:
    if os.environ.get("FIVERR_SESSION_COOKIE", ""):
        results = _scrape_buyer_requests(keywords)
        if results:
            return results
    return _fallback_google(keywords)
