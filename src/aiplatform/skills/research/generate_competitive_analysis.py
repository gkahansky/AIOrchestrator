"""
Skill: generate_competitive_analysis
Benchmark a podcast against up to 3 competing shows.

Methodology (based on market-competitors framework):
  1. Fetch each competitor landing page (direct HTTP)
  2. Extract visible text
  3. Pass all profiles to Claude for analysis across 5 dimensions:
     Messaging, Positioning, Content Strategy, Social Signals, Differentiation Gaps
  4. Produce: individual SWOT + aggregate positioning map + steal-worthy tactics

Input:
    show_context        dict       — {show_name, niche, audience, host_name, show_notes}
    competitor_urls     list[str]  — 1-3 competitor show website URLs
    brand_voice_injection str      — optional
    max_tokens          int        — default 8192

Output:
    {
        "competitors":         list[dict],   # [{url, name, page_text_excerpt, fetch_error}]
        "swot_analysis":       str,          # per-competitor SWOT + aggregate
        "positioning_map":     str,          # 2-axis positioning description
        "content_gaps":        list[str],    # topics competitors cover that the show doesn't
        "steal_worthy_tactics": list[str],   # specific tactics worth adopting
        "strategic_recommendations": list[str],
        "raw_report":          str,
        "cost_usd":            float,
    }
"""

from __future__ import annotations

import os
import re


SYSTEM_PROMPT = """\
You are a competitive intelligence analyst specialising in podcasts and content marketing.
Your job is to help podcast hosts understand their competitive landscape and find clear,
actionable differentiation opportunities.

Be specific. Name what competitors do well and what they do poorly. Identify the exact
messaging angles, content formats, or audience segments that are underserved.
Generic observations ("they focus on education") are useless. Surface the actual tactics.
"""

_SECTION_PATTERN = re.compile(
    r"===SECTION:\s*(.+?)===(.*?)(?====SECTION:|===CONTENT_GAPS|===STEAL_WORTHY|===STRATEGIC|$)",
    re.DOTALL | re.IGNORECASE,
)
_LIST_SECTION = re.compile(
    r"===(CONTENT_GAPS|STEAL_WORTHY_TACTICS|STRATEGIC_RECOMMENDATIONS)===(.*?)(?====|$)",
    re.DOTALL | re.IGNORECASE,
)


def generate_competitive_analysis(
    show_context: dict,
    competitor_urls: list[str],
    brand_voice_injection: str = "",
    max_tokens: int = 8192,
) -> dict:
    """
    Fetch competitor pages and produce a full competitive analysis report.
    Requires ANTHROPIC_API_KEY.
    """
    import anthropic

    competitors = _fetch_competitors(competitor_urls[:3])

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    user_message = _build_prompt(show_context, competitors, brand_voice_injection)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    parsed = _parse_report(raw)

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )

    return {
        "competitors":               competitors,
        "swot_analysis":             parsed.get("swot_analysis", ""),
        "positioning_map":           parsed.get("positioning_map", ""),
        "content_gaps":              parsed.get("content_gaps", []),
        "steal_worthy_tactics":      parsed.get("steal_worthy_tactics", []),
        "strategic_recommendations": parsed.get("strategic_recommendations", []),
        "raw_report":                raw,
        "cost_usd":                  cost_usd,
    }


# ─── Page fetcher ─────────────────────────────────────────────────────────────

def _fetch_competitors(urls: list[str]) -> list[dict]:
    results = []
    for url in urls:
        entry: dict = {"url": url, "name": _url_to_name(url), "page_text_excerpt": "", "fetch_error": None}
        try:
            import requests
            resp = requests.get(
                url, timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (compatible; EchoForgeAuditBot/1.0)"},
            )
            resp.raise_for_status()
            cleaned = _strip_html(resp.text)
            entry["page_text_excerpt"] = cleaned[:6000]
        except Exception as exc:
            entry["fetch_error"] = str(exc)
        results.append(entry)
    return results


def _url_to_name(url: str) -> str:
    # Extract domain as a readable show name placeholder
    return re.sub(r"https?://(www\.)?", "", url).split("/")[0]


def _strip_html(html: str) -> str:
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s{2,}", "\n", html)
    return html.strip()


# ─── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(ctx: dict, competitors: list[dict], brand_voice_injection: str) -> str:
    show = ctx.get("show_name", "the podcast")
    niche = ctx.get("niche", "general")
    audience = ctx.get("audience", "general audience")
    host = ctx.get("host_name", "")
    show_notes = ctx.get("show_notes", "")[:800]

    bv = f"\nBRAND VOICE:\n{brand_voice_injection.strip()}\n" if brand_voice_injection.strip() else ""
    host_line = f"Host: {host}\n" if host else ""
    notes_block = f"\nRecent episode excerpt:\n{show_notes}\n" if show_notes else ""

    competitor_blocks = []
    for i, c in enumerate(competitors, 1):
        if c.get("fetch_error"):
            competitor_blocks.append(
                f"COMPETITOR {i}: {c['name']} ({c['url']})\n"
                f"[Page could not be fetched: {c['fetch_error']}]"
            )
        else:
            competitor_blocks.append(
                f"COMPETITOR {i}: {c['name']} ({c['url']})\n"
                f"{c['page_text_excerpt']}"
            )

    competitor_section = "\n\n---\n\n".join(competitor_blocks)

    return f"""\
Analyse the competitive landscape for the podcast described below against {len(competitors)} competing show(s).

OUR SHOW:
Show: {show}
Niche: {niche}
Audience: {audience}
{host_line}{bv}{notes_block}
COMPETITOR PAGES:
{competitor_section}

Produce a comprehensive competitive analysis with the following sections:

===SECTION: Individual SWOT===
For each competitor: Strengths | Weaknesses | Opportunities (for us) | Threats (to us).
Be specific — use actual copy and positioning from their pages.

===SECTION: Aggregate SWOT===
Combined SWOT across all competitors. What patterns emerge?

===SECTION: Positioning Map===
Describe where each show sits on two axes most relevant to this niche
(e.g. Beginner ↔ Advanced, Tactical ↔ Inspirational, Niche ↔ Broad).
Where is our show? Where is the underserved white space?

===CONTENT_GAPS===
List 5-8 specific topic angles or content formats that competitors cover where our show
has clear opportunity to differentiate or go deeper. One item per line, starting with a dash.

===STEAL_WORTHY_TACTICS===
List 5-6 specific tactics used by competitors that are worth adapting (not copying).
For each: what the tactic is + why it works + how our show could adapt it.

===STRATEGIC_RECOMMENDATIONS===
List 5 concrete next steps for our show, ordered by expected impact. Be specific.
"""


# ─── Parser ───────────────────────────────────────────────────────────────────

def _parse_report(raw: str) -> dict:
    result: dict = {}

    # Named sections (SWOT, Positioning)
    swot_parts = []
    for match in _SECTION_PATTERN.finditer(raw):
        name = match.group(1).strip().lower()
        body = match.group(2).strip()
        if "swot" in name:
            swot_parts.append(body)
        elif "positioning" in name:
            result["positioning_map"] = body
    result["swot_analysis"] = "\n\n".join(swot_parts)

    # List sections
    for match in _LIST_SECTION.finditer(raw):
        key = match.group(1).lower()
        body = match.group(2).strip()
        items = [
            re.sub(r"^[-•*\d.]+\s*", "", line).strip()
            for line in body.splitlines()
            if line.strip() and not line.strip().startswith("===")
        ]
        items = [i for i in items if i]
        result[key] = items

    return result
