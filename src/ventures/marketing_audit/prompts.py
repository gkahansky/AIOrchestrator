"""
Marketing Audit prompts — tier-aware website analysis via Claude API.

Claude is asked to return a single JSON object with no surrounding text.
The JSON schema matches what generate_pdf_report.py expects as input.
"""

import json
from ventures.marketing_audit.config import DIMENSION_WEIGHT_LABELS


SYSTEM_PROMPT = """\
You are a senior marketing strategist conducting a professional website audit \
for a client. You have deep expertise in CRO, copywriting, SEO, and competitive \
positioning. Your analysis is specific, evidence-based, and commercially focused.

IMPORTANT: You must respond with valid JSON only — no markdown fences, no commentary, \
no text before or after the JSON object. The JSON must match the schema provided exactly.\
"""


def build_audit_prompt(order: dict, scraped: dict) -> str:
    """
    Build the Claude user message for a tier-aware audit.

    Scoring instructions are IDENTICAL for all tiers so that dimension scores
    are computed with the same framing regardless of which report a client ordered.
    The tier only controls which optional output sections Claude populates.

    Args:
        order:   Order dict with url, tier, competitor_urls, brand_name.
        scraped: Output from scrape_website skill — {target, competitors}.
    """
    tier = order["tier"]
    url = order["url"]
    brand_name = order.get("brand_name", _extract_brand(url))

    target = scraped.get("target", {})
    competitors = scraped.get("competitors", [])

    scraped_summary = _summarise_scraped(target, competitors, scraped.get("accessibility_audit", {}))
    client_context_block = _build_client_context(order)

    # Tier controls OUTPUT SCOPE only — not scoring depth.
    # This is what keeps dimension scores consistent across tiers.
    tier_output_scope = {
        "snapshot": """\
OUTPUT SCOPE — Snapshot tier:
- categories: score, key_finding, AND details for all 7 dimensions (always required)
- findings: all issues found (8-15 items across all severity levels)
- quick_wins: 5-7 specific actions
- medium_term: leave as empty array []
- strategic: leave as empty array []
- copy_examples: leave as empty array []
- competitors: leave as empty array []
- roadmap: leave as empty string ""
""",
        "full": """\
OUTPUT SCOPE — Full Audit tier:
- categories: score, key_finding, AND details for all 7 dimensions (always required)
- findings: all issues found (8-15 items)
- quick_wins: 5-7 specific actions
- medium_term: 4-6 actions (1-3 month horizon)
- strategic: 3-5 initiatives (3-6 month horizon)
- copy_examples: exactly 2 before/after rewrites for the highest-impact pages/issues
- competitors: summarise each scraped competitor in the competitors array
- roadmap: leave as empty string ""
""",
        "premium": """\
OUTPUT SCOPE — Audit + Strategy tier:
- categories: score, key_finding, AND details for all 7 dimensions (always required)
- findings: all issues found (10-18 items)
- quick_wins: 5-7 specific actions
- medium_term: 4-6 actions (1-3 month horizon)
- strategic: 3-5 initiatives (3-6 month horizon)
- copy_examples: exactly 3 before/after rewrites
- competitors: full deep-dive comparison of all scraped competitor sites
- roadmap: a 30-day implementation plan as a markdown string. Use ## Week 1 / ## Week 2 / \
## Week 3 / ## Week 4 headers. Each week: 4-6 specific tasks with named owners \
(e.g. "Founder", "Designer", "Content writer"). Use real page names, real copy \
suggestions, and real metric targets where possible.
""",
    }

    schema = """\
{
  "brand_name": "string",
  "business_type": "SaaS | Agency | E-commerce | Local | Creator | Marketplace | Other",
  "overall_score": 0-100,
  "executive_summary": "string — 3-5 paragraphs for a non-technical stakeholder",
  "categories": {
    "Content & Messaging":     {"score": 0-100, "key_finding": "string", "details": "string — 2-3 paragraphs of specific evidence and recommendations"},
    "Conversion Optimization": {"score": 0-100, "key_finding": "string", "details": "string — 2-3 paragraphs"},
    "SEO & Discoverability":   {"score": 0-100, "key_finding": "string", "details": "string — 2-3 paragraphs"},
    "Competitive Positioning": {"score": 0-100, "key_finding": "string", "details": "string — 2-3 paragraphs"},
    "Brand & Trust":           {"score": 0-100, "key_finding": "string", "details": "string — 2-3 paragraphs"},
    "Accessibility & UX":      {"score": 0-100, "key_finding": "string", "details": "string — Include WCAG 2.1 summary based directly on the provided scrape data, outline specific violations to give remediation steps."},
    "Growth & Strategy":       {"score": 0-100, "key_finding": "string", "details": "string — 2-3 paragraphs"}
  },
  "findings": [
    {
      "severity": "Critical | High | Medium | Low",
      "problem": "string — what is wrong, stated as a fact (1-2 sentences)",
      "impact": "string — business consequence of leaving this unfixed (1-2 sentences)",
      "fix": "string — specific, actionable resolution steps (1-3 sentences)"
    }
  ],
  "quick_wins": ["string — specific action, not generic advice"],
  "medium_term": ["string"],
  "strategic":   ["string"],
  "copy_examples": [
    {"page": "string", "issue": "string", "before": "string", "after": "string"}
  ],
  "competitors": [
    {
      "name": "string",
      "url": "string",
      "positioning": "string — their main value prop",
      "pricing": "string — pricing model/range if detectable",
      "social_proof": "string — trust signals observed",
      "content": "string — content quality/depth",
      "vs_target": "string — where they beat or lag the target site"
    }
  ],
  "roadmap": "string — markdown (empty string for non-premium tiers)"
}"""

    return f"""\
Audit the following website and return a JSON object matching the schema below.

URL: {url}
BRAND: {brand_name}

SCORING INSTRUCTIONS (apply identically for all tiers):
Evaluate all 6 dimensions on a 0-100 scale. Be specific and evidence-based. \
A score of 50 means average — use the full range. Scores must reflect the actual \
quality of the site and must NOT be adjusted based on the tier the client purchased.
{client_context_block}
{tier_output_scope[tier]}
SCORING WEIGHTS (use when computing overall_score):
{json.dumps(DIMENSION_WEIGHT_LABELS, indent=2)}

SCRAPED DATA FROM THE SITE:
{scraped_summary}

JSON SCHEMA TO RETURN (return only the JSON, nothing else):
{schema}
"""


def parse_audit_response(text: str, tier: str, url: str) -> dict:
    """
    Parse the Claude JSON response into the report data dict.
    Falls back gracefully if JSON is malformed.
    """
    from datetime import datetime
    from ventures.marketing_audit.config import DIMENSION_WEIGHT_LABELS

    # Strip accidental markdown fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned invalid JSON: {exc}\n\nRaw text:\n{text[:500]}")

    # Normalise categories to match generate_pdf_report.py format
    categories = data.get("categories", {})
    normalised_categories = {}
    for dim, label in DIMENSION_WEIGHT_LABELS.items():
        cat = categories.get(dim, {})
        normalised_categories[dim] = {
            "score": int(cat.get("score", 50)),
            "weight": label,
            "key_finding": cat.get("key_finding", ""),
            "details": cat.get("details", ""),
        }
    data["categories"] = normalised_categories

    # Ensure required top-level fields
    data.setdefault("url", url)
    data.setdefault("date", datetime.now().strftime("%B %d, %Y"))
    data.setdefault("tier", tier)
    data.setdefault("findings", [])
    data.setdefault("quick_wins", [])
    data.setdefault("medium_term", [])
    data.setdefault("strategic", [])
    data.setdefault("copy_examples", [])
    data.setdefault("competitors", [])
    data.setdefault("roadmap", "")

    # Recompute overall_score from weighted category scores (authoritative)
    from ventures.marketing_audit.config import DIMENSION_WEIGHTS
    weighted = sum(
        normalised_categories.get(dim, {}).get("score", 50) * w
        for dim, w in DIMENSION_WEIGHTS.items()
    )
    data["overall_score"] = round(weighted)

    return data


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_client_context(order: dict) -> str:
    """
    Build a CLIENT CONTEXT block from optional order fields.
    Returns an empty string if none of the context fields are present,
    so the prompt degrades gracefully for orders without enriched context.
    """
    fields = [
        ("audience",          "Target audience"),
        ("conversion_goal",   "Primary conversion goal"),
        ("weak_spots",        "Known weak spots"),
        ("traffic_source",    "Primary traffic source"),
        ("team_size",         "Team size"),
        ("budget",            "Budget posture"),
        ("growth_channel",    "Growth channel priorities"),
        ("milestones",        "Upcoming milestones"),
        ("email_list_size",   "Email list size"),
    ]
    lines = []
    for key, label in fields:
        val = order.get(key, "").strip() if isinstance(order.get(key), str) else ""
        if val:
            lines.append(f"- {label}: {val}")

    if not lines:
        return ""

    return "\nCLIENT CONTEXT (provided by the client — use this to make the audit more specific):\n" + "\n".join(lines) + "\n"


def _extract_brand(url: str) -> str:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.replace("www.", "")
    return host.split(".")[0].title()


def _summarise_scraped(target: dict, competitors: list, accessibility: dict = None) -> str:
    """Compact summary of scraped data to keep prompt size manageable."""
    analysis = target.get("analysis", {})

    seo = analysis.get("seo", {})
    conv = analysis.get("conversion", {})
    trust = analysis.get("trust", {})
    tracking = analysis.get("tracking", {})
    content = analysis.get("content", {})
    crawl = analysis.get("crawl", {})

    pages_fetched = crawl.get("pages_fetched", target.get("pages_crawled", 1))
    page_urls = crawl.get("page_urls", [target.get("url", "")])

    lines = [
        f"--- TARGET SITE ---",
        f"Pages crawled: {pages_fetched} — all metrics below are aggregated across all pages",
        f"Pages: {page_urls[:20]}",  # show up to 20 so Claude knows which subpages were seen
        f"Title: {seo.get('title', 'N/A')} (length {seo.get('title_length', 0)},"
        f" ok={seo.get('title_ok', False)})",
        f"Meta description: {seo.get('meta_description', 'MISSING')[:120]}",
        f"H1 tags: {seo.get('headings', {}).get('h1', [])}",
        f"H2 tags (first 5): {(seo.get('headings') or {}).get('h2', [])[:5]}",
        f"Heading issues: {seo.get('heading_issues', [])}",
        f"Word count (all pages combined): {content.get('word_count', 0)}",
        f"CTAs found ({conv.get('cta_count', 0)} across all pages): "
        f"{[c.get('text') for c in conv.get('ctas', [])[:8]]}",
        f"Forms found (all pages): {conv.get('form_count', 0)}",
        f"Social links: {[s.get('platform') for s in trust.get('social_links', [])]}",
        f"Tracking tools: {tracking.get('tools_detected', [])}",
        f"Schema types: {tracking.get('schema_types', [])}",
        f"Images without alt: {seo.get('images_without_alt', 0)}/{seo.get('images_total', 0)}",
        f"Has viewport meta: {seo.get('has_viewport', False)}",
        f"Robots.txt: {analysis.get('robots', {}).get('exists', False)}",
        f"Sitemap: {analysis.get('sitemap', {}).get('exists', False)}",
        f"OG tags: {list(seo.get('og_tags', {}).keys())}",
    ]

    if accessibility and "wcag_score" in accessibility:
        lines.append(f"\n--- ACCESSIBILITY AUDIT (WCAG 2.1) ---")
        lines.append(f"WCAG Compliance Score: {accessibility.get('wcag_score')}/100")
        lines.append(f"Total Violations: {len(accessibility.get('violations', []))}")
        lines.append(f"Top Violations: {[v.get('id') for v in accessibility.get('violations', [])[:5]]}")
        lines.append(f"Incomplete/Needs Review: {len(accessibility.get('incomplete', []))}")

    if competitors:
        lines.append("\n--- COMPETITORS ---")
        for comp in competitors:
            if comp.get("status") == "error":
                lines.append(f"{comp['url']}: scrape failed")
                continue
            cd = comp.get("data", {})
            pos = cd.get("positioning", {})
            ctas = cd.get("ctas", [])
            cta_count = len(ctas) if isinstance(ctas, list) else (ctas.get("count", 0) if isinstance(ctas, dict) else 0)
            social = cd.get("social_links", [])
            social_count = len(social) if isinstance(social, list) else (social.get("count", 0) if isinstance(social, dict) else 0)
            lines.append(
                f"{comp.get('domain', comp['url'])}: "
                f"headline={pos.get('h1_tags', ['?'])[:1]}, "
                f"CTAs={cta_count}, "
                f"social_links={social_count}"
            )

    return "\n".join(lines)






