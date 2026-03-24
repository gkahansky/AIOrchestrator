"""
Marketing Audit prompts — tier-aware website analysis via Claude API.

Claude is asked to return a single JSON object with no surrounding text.
The JSON schema matches what generate_pdf_report.py expects as input.
"""

import json
from ventures.marketing_audit.config import TIERS, DIMENSION_WEIGHT_LABELS


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

    Args:
        order:   Order dict with url, tier, competitor_urls, brand_name.
        scraped: Output from scrape_website skill — {target, competitors}.
    """
    tier = order["tier"]
    depth = TIERS[tier]["depth"]
    url = order["url"]
    brand_name = order.get("brand_name", _extract_brand(url))

    target = scraped.get("target", {})
    competitors = scraped.get("competitors", [])

    # Summarise scraped data so prompt stays within token budget
    scraped_summary = _summarise_scraped(target, competitors)

    tier_instructions = {
        "snapshot": """\
TIER: Snapshot ($49)
Generate only: overall_score, executive_summary (2 paragraphs max), and 5 quick_wins.
For categories, provide scores and key_finding only (no details field required).
Leave medium_term, strategic, competitors, and roadmap as empty arrays/strings.""",

        "full": """\
TIER: Full Audit ($149)
Generate: all 6 dimension scores with detailed findings, 2-3 findings per dimension.
Include copy_examples: 2 before/after copy rewrites for the highest-impact issues.
Competitors: summarise each of the scraped competitor sites in the competitors array.
Leave roadmap as empty string.""",

        "premium": """\
TIER: Audit + Strategy ($249)
Generate: all 6 dimension scores with detailed findings.
Include copy_examples: 3 before/after copy rewrites.
Competitors: full comparison of all scraped competitor sites.
roadmap: A 30-day implementation plan as a markdown string — Week 1/2/3/4 sections \
with specific daily tasks and owners (e.g. "Founder", "Designer", "Content writer").""",
    }

    schema = """\
{
  "brand_name": "string",
  "business_type": "SaaS | Agency | E-commerce | Local | Creator | Marketplace | Other",
  "overall_score": 0-100,
  "executive_summary": "string — 3-5 paragraphs for a non-technical stakeholder",
  "categories": {
    "Content & Messaging":    {"score": 0-100, "key_finding": "string", "details": "string"},
    "Conversion Optimization": {"score": 0-100, "key_finding": "string", "details": "string"},
    "SEO & Discoverability":  {"score": 0-100, "key_finding": "string", "details": "string"},
    "Competitive Positioning": {"score": 0-100, "key_finding": "string", "details": "string"},
    "Brand & Trust":          {"score": 0-100, "key_finding": "string", "details": "string"},
    "Growth & Strategy":      {"score": 0-100, "key_finding": "string", "details": "string"}
  },
  "findings": [
    {"severity": "Critical | High | Medium | Low", "finding": "string — specific and actionable"}
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
{tier_instructions[depth]}

SCORING WEIGHTS (use these when computing overall_score):
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

def _extract_brand(url: str) -> str:
    from urllib.parse import urlparse
    host = urlparse(url).netloc.replace("www.", "")
    return host.split(".")[0].title()


def _summarise_scraped(target: dict, competitors: list) -> str:
    """Compact summary of scraped data to keep prompt size manageable."""
    analysis = target.get("analysis", {})

    seo = analysis.get("seo", {})
    conv = analysis.get("conversion", {})
    trust = analysis.get("trust", {})
    tracking = analysis.get("tracking", {})
    content = analysis.get("content", {})

    lines = [
        f"--- TARGET SITE ---",
        f"Title: {seo.get('title', 'N/A')} (length {seo.get('title_length', 0)},"
        f" ok={seo.get('title_ok', False)})",
        f"Meta description: {seo.get('meta_description', 'MISSING')[:120]}",
        f"H1 tags: {seo.get('headings', {}).get('h1', [])}",
        f"H2 tags (first 5): {(seo.get('headings') or {}).get('h2', [])[:5]}",
        f"Heading issues: {seo.get('heading_issues', [])}",
        f"Word count: {content.get('word_count', 0)}",
        f"CTAs found ({conv.get('cta_count', 0)}): "
        f"{[c.get('text') for c in conv.get('ctas', [])[:5]]}",
        f"Forms: {conv.get('form_count', 0)}",
        f"Social links: {[s.get('platform') for s in trust.get('social_links', [])]}",
        f"Tracking tools: {tracking.get('tools_detected', [])}",
        f"Schema types: {tracking.get('schema_types', [])}",
        f"Images without alt: {seo.get('images_without_alt', 0)}/{seo.get('images_total', 0)}",
        f"Has viewport meta: {seo.get('has_viewport', False)}",
        f"Robots.txt: {target.get('analysis', {}).get('robots', {}).get('exists', False)}",
        f"Sitemap: {target.get('analysis', {}).get('sitemap', {}).get('exists', False)}",
        f"OG tags: {list(seo.get('og_tags', {}).keys())}",
    ]

    if competitors:
        lines.append("\n--- COMPETITORS ---")
        for comp in competitors:
            if comp.get("status") == "error":
                lines.append(f"{comp['url']}: scrape failed")
                continue
            cd = comp.get("data", {})
            pos = cd.get("positioning", {})
            lines.append(
                f"{comp.get('domain', comp['url'])}: "
                f"headline={pos.get('h1_tags', ['?'])[:1]}, "
                f"CTAs={cd.get('ctas', {}).get('count', 0)}, "
                f"social_links={cd.get('social_links', {}).get('count', 0)}"
            )

    return "\n".join(lines)
