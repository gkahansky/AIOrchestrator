"""
Skill: generate_audit_report
Run a marketing audit on a scraped website via Claude API.
Returns structured report data for PDF/Markdown generation.

Input:
    order:   dict with url, tier ("snapshot"|"full"|"premium"), brand_name (optional),
             competitor_urls (optional list[str])
    scraped: output from scrape_website skill — {target, competitors}

Output:
    {
        "url":               str,
        "date":              str,
        "brand_name":        str,
        "business_type":     str,
        "tier":              str,
        "overall_score":     int,   # 0-100, computed from weighted category scores
        "executive_summary": str,
        "categories": {
            "Content & Messaging":    {"score": int, "weight": "25%", "key_finding": str, "details": str},
            "Conversion Optimization":{"score": int, "weight": "20%", ...},
            "SEO & Discoverability":  {"score": int, "weight": "20%", ...},
            "Competitive Positioning":{"score": int, "weight": "15%", ...},
            "Brand & Trust":          {"score": int, "weight": "10%", ...},
            "Growth & Strategy":      {"score": int, "weight": "10%", ...},
        },
        "findings":      [{"severity": str, "finding": str}, ...],
        "quick_wins":    [str, ...],
        "medium_term":   [str, ...],
        "strategic":     [str, ...],
        "copy_examples": [{"page": str, "issue": str, "before": str, "after": str}, ...],
        "competitors":   [{"name": str, "positioning": str, ...}, ...],
        "roadmap":       str,   # markdown — populated for premium tier only
        "cost_usd":      float,
    }
"""

import os

import anthropic


def generate_audit_report(order: dict, scraped: dict) -> dict:
    """
    Analyse a scraped website and return structured audit report data.

    Uses Claude API with a tier-aware prompt. The response is a single JSON object
    parsed and normalised by prompts.parse_audit_response().
    """
    # Import here to avoid circular deps at module load time
    from ventures.marketing_audit.prompts import build_audit_prompt, parse_audit_response
    from ventures.marketing_audit.config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS

    tier = order.get("tier", "full")
    url = order["url"]

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system = (
        "You are a senior marketing strategist. "
        "Respond with valid JSON only — no markdown fences, no text before or after."
    )
    user_message = build_audit_prompt(order, scraped)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = response.content[0].text

    # Claude Sonnet 4.6: $3/M input + $15/M output tokens
    cost_usd = round(
        response.usage.input_tokens * 0.000003 + response.usage.output_tokens * 0.000015,
        4,
    )

    report_data = parse_audit_response(raw_text, tier, url)
    report_data["cost_usd"] = cost_usd
    return report_data
