"""
Skill: generate_fiverr_gig
Generate a complete Fiverr gig content package for any venture using Claude API.

Given a venture service definition, this skill produces:
  - SEO-optimised gig title (max 80 chars, starts with "I will")
  - Gig description (Fiverr markdown, 1200–2400 chars)
  - Pricing packages (Basic / Standard / Premium)
  - FAQ (5 Q&A pairs addressing real buyer concerns)
  - Tags (5 tags, max 20 chars each)

Note: Fiverr has no public API for gig creation.
Output is saved as a structured JSON file for human review before manual Fiverr upload.

This skill is venture-agnostic. All venture-specific data is injected by the caller.
Never import from /ventures/ here.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


def generate_gig(
    service_name: str,
    service_description: str,
    packages: list[dict],
    target_audience: str,
    key_benefits: list[str],
    keywords: list[str],
    venture_name: str,
    output_dir: str | None = None,
    api_key: str | None = None,
) -> dict:
    """
    Capability: marketplace-write
    Generate a complete Fiverr gig content package for any venture service.

    Args:
        service_name:        Short service name (e.g. "Podcast Show Notes & Marketing Kit")
        service_description: 2–3 sentence plain-text description of what the service delivers
        packages:            List of 3 dicts (Basic → Standard → Premium):
                             [{name, price_usd, delivery_days, revisions, includes: [str]}]
        target_audience:     One sentence describing the ideal buyer
        key_benefits:        3–5 bullet points — outcomes/benefits, not features
        keywords:            5–10 search terms buyers use on Fiverr
        venture_name:        Slug for output file naming (e.g. "podcast_notes", "marketing_audit")
        output_dir:          Directory to save JSON (default: output/gigs/{venture_name}/)
        api_key:             Anthropic API key (falls back to ANTHROPIC_API_KEY env var)

    Returns:
        {
            category: str,
            subcategory: str,
            service_type: str,
            gig_metadata: dict[str, str],
            gig_title: str,
            gig_description: str,
            packages: [{name, price, delivery_days, revisions, description, features: [str]}],
            faq: [{question: str, answer: str}],
            requirements: [{requirement: str, is_mandatory: bool, type: str}],
            tags: [str],
            image_prompt: str,
            output_path: str,
        }
    """
    import anthropic

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set and no api_key provided.")

    client = anthropic.Anthropic(api_key=key)

    packages_text = "\n".join(
        f"  - {p['name']}: ${p['price_usd']}, {p['delivery_days']} day(s), "
        f"{p['revisions']} revision(s), includes: {', '.join(p.get('includes', []))}"
        for p in packages
    )
    benefits_text = "\n".join(f"  - {b}" for b in key_benefits)
    keywords_text = ", ".join(keywords)

    prompt = f"""You are an expert Fiverr seller writing a high-converting gig listing.
Generate a complete gig content package for the service below.

SERVICE DETAILS
Service name: {service_name}
Description: {service_description}
Target audience: {target_audience}

KEY BENEFITS (outcomes, not features)
{benefits_text}

PRICING PACKAGES (use these exact prices / delivery / revisions)
{packages_text}

SEARCH KEYWORDS buyers use
{keywords_text}

Return ONLY valid JSON matching this exact structure — no markdown fences, no commentary:

{{
  "category": "<The overarching Fiverr category, e.g. 'Writing & Translation', 'Digital Marketing'>",
  "subcategory": "<The subcategory, e.g. 'Podcast Writing', 'Marketing Strategy'>",
  "service_type": "<The specific service type, e.g. 'Show Notes', 'Consultation'>",
  "gig_metadata": {{
    "<Metadata key 1 (e.g. Language)>": "<Value 1>",
    "<Metadata key 2 (e.g. Industry)>": "<Value 2>"
  }},
  "gig_title": "<80-char SEO title starting with 'I will' — specific and benefit-driven>",
  "gig_description": "<STRICTLY under 1200 chars Fiverr description — use **bold** for section headers; include: hook paragraph, what you get (bullet list), why choose me, process overview (numbered), CTA>",
  "packages": [
    {{
      "name": "Basic",
      "price": <int USD>,
      "delivery_days": <int>,
      "revisions": <int>,
      "description": "<STRICTLY under 100 characters — what this tier delivers>",
      "features": ["<feature 1>", "<feature 2>", "<feature 3>"]
    }},
    {{
      "name": "Standard",
      "price": <int USD>,
      "delivery_days": <int>,
      "revisions": <int>,
      "description": "<STRICTLY under 100 characters>",
      "features": ["<feature 1>", "<feature 2>", "<feature 3>", "<feature 4>"]
    }},
    {{
      "name": "Premium",
      "price": <int USD>,
      "delivery_days": <int>,
      "revisions": <int>,
      "description": "<STRICTLY under 100 characters>",
      "features": ["<feature 1>", "<feature 2>", "<feature 3>", "<feature 4>", "<feature 5>"]
    }}
  ],
  "faq": [
    {{"question": "<buyer question>", "answer": "<clear, reassuring answer>"}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}},
    {{"question": "...", "answer": "..."}}
  ],
  "requirements": [
    {{"requirement": "<Question or instruction for the buyer to provide before work can start>", "is_mandatory": true, "type": "<text | attachment>"}},
    {{"requirement": "...", "is_mandatory": true, "type": "text"}}
  ],
  "tags": ["<tag1>", "<tag2>", "<tag3>", "<tag4>", "<tag5>"],
  "image_prompt": "<detailed midjourney-style image prompt for a 16:9 gig cover image showing a minimal, professional, abstract visual representation of the service, WITHOUT text or typography>"
}}

Rules:
- gig_title must start with "I will" and be under 80 characters total
- gig_description MUST be under 1200 characters total, persuasive, NOT generic
- packages description MUST be under 100 characters total each
- prices MUST be multiples of 5 (e.g. 30, 80, 150)
- packages must match the exact delivery_days / revisions from the input
- faq must address real buyer concerns: turnaround, revisions, formats, niche experience, communication
- tags must be max 20 characters each and highly relevant search terms
"""

    log.info("Generating Fiverr gig content for '%s'...", venture_name)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if Claude wrapped the JSON
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    gig = json.loads(raw)

    # Save output
    out_dir = Path(output_dir) if output_dir else Path("output") / "gigs" / venture_name
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{venture_name}-fiverr-gig-{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(gig, f, indent=2, ensure_ascii=False)

    log.info("Saved to %s", out_path)
    gig["output_path"] = str(out_path)
    return gig
