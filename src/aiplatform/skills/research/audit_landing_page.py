"""
Skill: audit_landing_page
Fetch a web page and produce a scored CRO audit using the 7-point framework.

Scoring sections:
  1. Hero        — headline, subheadline, above-fold CTA
  2. Value Prop  — clarity, uniqueness, specificity
  3. Social Proof — testimonials, listener count, press mentions
  4. Features    — episode/format descriptions, what listeners gain
  5. Objections  — addressing hesitation to subscribe/listen
  6. CTA         — subscribe buttons, links, placement, friction
  7. Footer      — links, contact, legal, trust signals

Each section scored 1–10. Overall score = mean of section scores.
Priority fixes ordered by effort-to-impact ratio.

Input:
    url             str    — page URL to audit
    page_context    dict   — optional {show_name, niche, audience} for benchmark framing
    max_tokens      int    — default 6144

Output:
    {
        "overall_score":  float,
        "sections":       list[dict],   # [{name, score, findings, recommendations}]
        "priority_fixes": list[str],
        "ab_tests":       list[str],
        "raw_report":     str,
        "cost_usd":       float,
    }

Errors:
    FetchError      — page could not be retrieved (network / auth / JS-only)
    PageTooLarge    — page content exceeds 80 000 characters after cleaning
"""

from __future__ import annotations

import os
import re


SYSTEM_PROMPT = """\
You are a conversion rate optimisation (CRO) specialist auditing podcast landing pages.
Score each section 1-10 based on how well it converts a first-time visitor into a subscriber.

Scoring rubric:
  9-10 Best-in-class: clear, specific, benefit-led, no friction
  7-8  Good: does the job, minor gaps
  5-6  Average: generic or missing key elements
  3-4  Weak: confusing, buried, or contradictory
  1-2  Missing or actively harmful to conversion

Always:
- Quote the actual page copy when citing problems (max 125 chars per quote)
- Connect every recommendation to a specific revenue or growth outcome
- Order priority fixes by effort-to-impact ratio (quick wins first)
- Be specific. "Rewrite the hero headline to include the audience and primary benefit" beats "improve the headline".
"""

_SECTION_NAMES = [
    "Hero", "Value Prop", "Social Proof",
    "Features", "Objections", "CTA", "Footer",
]

_SECTION_PATTERN = re.compile(
    r"===SECTION:\s*(.+?)===(.*?)(?====SECTION:|===PRIORITY|===AB_TESTS|$)",
    re.DOTALL | re.IGNORECASE,
)
_PRIORITY_PATTERN = re.compile(
    r"===PRIORITY_FIXES===(.*?)(?====|$)", re.DOTALL | re.IGNORECASE,
)
_AB_PATTERN = re.compile(
    r"===AB_TESTS===(.*?)(?====|$)", re.DOTALL | re.IGNORECASE,
)
_SCORE_PATTERN = re.compile(r"Score:\s*(\d+(?:\.\d+)?)\s*/\s*10", re.IGNORECASE)
_FIELD_PATTERN = re.compile(
    r"^(Score|Findings|Recommendations):\s*(.+?)(?=\n(?:Score|Findings|Recommendations):|$)",
    re.MULTILINE | re.DOTALL,
)


class FetchError(Exception):
    pass


class PageTooLarge(Exception):
    pass


def audit_landing_page(
    url: str,
    page_context: dict | None = None,
    max_tokens: int = 6144,
) -> dict:
    """
    Fetch url and produce a scored CRO audit.
    Requires ANTHROPIC_API_KEY.
    """
    import anthropic

    page_text = _fetch_page(url)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    ctx = page_context or {}
    user_message = _build_prompt(url, page_text, ctx)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()
    sections, priority_fixes, ab_tests = _parse_report(raw)

    scores = [s["score"] for s in sections if s["score"] is not None]
    overall = round(sum(scores) / len(scores), 1) if scores else 0.0

    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )

    return {
        "overall_score":  overall,
        "sections":       sections,
        "priority_fixes": priority_fixes,
        "ab_tests":       ab_tests,
        "raw_report":     raw,
        "cost_usd":       cost_usd,
    }


# ─── Page fetcher ─────────────────────────────────────────────────────────────

def _fetch_page(url: str) -> str:
    try:
        import requests
    except ImportError:
        raise FetchError("requests package not available — install it with `pip install requests`")

    try:
        resp = requests.get(
            url,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; EchoForgeAuditBot/1.0; "
                    "+https://echoforge.biz)"
                )
            },
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"Could not fetch {url}: {exc}") from exc

    html = resp.text
    cleaned = _strip_html(html)

    if len(cleaned) > 80_000:
        raise PageTooLarge(
            f"Page content is {len(cleaned):,} chars after cleaning — exceeds 80,000 char limit."
        )

    return cleaned


def _strip_html(html: str) -> str:
    # Remove script and style blocks
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML tags
    html = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    html = re.sub(r"\s{2,}", "\n", html)
    return html.strip()


# ─── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(url: str, page_text: str, ctx: dict) -> str:
    show = ctx.get("show_name", "")
    niche = ctx.get("niche", "")
    audience = ctx.get("audience", "")

    context_block = ""
    if show or niche or audience:
        context_block = (
            f"\nSHOW CONTEXT (for audience benchmark):\n"
            f"Show: {show}\nNiche: {niche}\nAudience: {audience}\n"
        )

    # Truncate page text to fit context window safely
    page_excerpt = page_text[:12000]

    sections_spec = "\n".join(
        f"  {s}" for s in _SECTION_NAMES
    )

    return f"""\
Audit this podcast landing page for conversion rate optimisation.

URL: {url}
{context_block}
PAGE CONTENT:
{page_excerpt}

Score each section 1-10 and provide specific findings and recommendations.

Output in this exact format:

===SECTION: Hero===
Score: X/10
Findings: [what you found — quote page copy where relevant, max 125 chars per quote]
Recommendations: [specific, actionable fixes with expected impact]

===SECTION: Value Prop===
Score: X/10
Findings: ...
Recommendations: ...

===SECTION: Social Proof===
Score: X/10
Findings: ...
Recommendations: ...

===SECTION: Features===
Score: X/10
Findings: ...
Recommendations: ...

===SECTION: Objections===
Score: X/10
Findings: ...
Recommendations: ...

===SECTION: CTA===
Score: X/10
Findings: ...
Recommendations: ...

===SECTION: Footer===
Score: X/10
Findings: ...
Recommendations: ...

===PRIORITY_FIXES===
List 5-8 fixes ordered by effort-to-impact (quick wins first):
1. [EFFORT: Low | IMPACT: High] ...
2. ...

===AB_TESTS===
List 3-5 A/B test hypotheses in format:
Test: [what to test]
Hypothesis: [if we change X, conversion will Y because Z]
Metric: [what to measure]
"""


# ─── Parser ───────────────────────────────────────────────────────────────────

def _parse_report(raw: str) -> tuple[list[dict], list[str], list[str]]:
    sections = []
    for match in _SECTION_PATTERN.finditer(raw):
        name = match.group(1).strip()
        block = match.group(2).strip()
        fields: dict[str, str] = {}
        for m in _FIELD_PATTERN.finditer(block):
            fields[m.group(1).lower()] = m.group(2).strip()
        score_match = _SCORE_PATTERN.search(fields.get("score", block))
        score = float(score_match.group(1)) if score_match else None
        sections.append({
            "name":            name,
            "score":           score,
            "findings":        fields.get("findings", ""),
            "recommendations": fields.get("recommendations", ""),
        })

    priority_fixes = []
    pm = _PRIORITY_PATTERN.search(raw)
    if pm:
        for line in pm.group(1).strip().splitlines():
            line = line.strip()
            if line and re.match(r"^\d+\.", line):
                priority_fixes.append(re.sub(r"^\d+\.\s*", "", line))

    ab_tests = []
    am = _AB_PATTERN.search(raw)
    if am:
        # Collect "Test:" blocks
        test_blocks = re.split(r"(?=\bTest:)", am.group(1), flags=re.IGNORECASE)
        for block in test_blocks:
            block = block.strip()
            if block.lower().startswith("test:"):
                ab_tests.append(block)

    return sections, priority_fixes, ab_tests
