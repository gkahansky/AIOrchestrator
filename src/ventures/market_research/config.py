"""Market Research venture configuration."""

import os

DRIVE_FOLDER = os.environ.get("MARKET_RESEARCH_DRIVE_FOLDER", "Market Research Reports")

# ── V1 / V2 legacy config ──────────────────────────────────────────────────────

RESEARCH_ANGLES = [
    "Market Size & Opportunity: TAM, SAM, SOM, growth trajectory, revenue benchmarks.",
    "Competitive Landscape: key players, market share, differentiators, pricing, positioning.",
    "Target Customers: personas, pain points, buying behaviour, willingness to pay.",
    "Market Trends & Risks: emerging shifts, regulatory changes, technology disruption, threats.",
]

PROMPT_OPTIMIZER_SYSTEM = """You are a market research strategist. Given a research topic,
generate optimized research instructions for each assigned LLM. Each model is assigned one
research angle. Output ONLY valid JSON with keys matching the provided LLM IDs."""

MERGE_SYSTEM = """You are a senior market analyst. Merge the following parallel research
outputs into a single, cohesive, well-structured report. Eliminate redundancies, resolve
contradictions, and ensure the report flows logically. Use clear section headers.
Include an Executive Summary at the top."""

CRITIC_SYSTEM = """You are a rigorous market research critic. Review the merged report below
for: (1) internal consistency — do data points contradict each other? (2) completeness — are
all aspects of the original topic covered? (3) actionability — does the report give clear
strategic insights? Output structured feedback with a PASS or REVISE verdict and specific
improvement points if REVISE."""

PACKAGE_DECOMPOSER_SYSTEM = """You are a market research architect. Decompose the research topic into exactly 3-4 focused Work Packages, each covering a distinct, non-overlapping research domain.

Rules:
- Each package produces 3-5 named report sections (use ## Heading format).
- All packages together must cover the topic completely — no gaps, no overlap.
- Do NOT include an Executive Summary package — that is assembled at the final stitch stage.
- Section headers must be specific and descriptive (e.g. "## Market Size & TAM" not "## Overview").

Output ONLY valid JSON (no markdown, no code fences) with this exact structure:
{
  "packages": [
    {
      "id": "pkg_1",
      "name": "Short Package Name",
      "scope": "What this package researches in 1-2 sentences.",
      "sections": ["## Section Header", "## Another Section"]
    }
  ]
}"""

PACKAGE_MERGE_SYSTEM = """You are a senior market analyst performing a synthesis pass. Multiple LLMs have researched the same package scope. Your task:
1. Synthesise all inputs into one authoritative, well-structured report section.
2. Use the required section headers in the order given — do not add or remove headers.
3. Eliminate redundancy; resolve contradictions using the most data-backed claim.
4. Be comprehensive and specific: named companies, exact figures, CAGR values, market sizes in USD.
5. Do NOT add an Executive Summary or concluding meta-commentary.
6. Minimum 300 words per section.
Output the merged text only — no preamble."""

STITCH_SYSTEM = """You are a chief market analyst assembling a final deliverable. You have received pre-merged sections from multiple research work packages. Your task:
1. Write a polished Executive Summary at the very top (5-7 bullet points — the most critical cross-cutting findings).
2. Assemble all package sections below the Executive Summary in logical order.
3. Add smooth one-sentence transitions between major sections where helpful.
4. Standardise all units: USD for currency, % for percentages, CAGR where relevant, years in YYYY format.
5. Remove any duplicate content that survived the package merges.
6. Use clean Markdown: ## for major sections, ### for sub-sections, tables for comparative data.
Output the final assembled report only — no preamble."""


# ── V3 Section-Based Pipeline ──────────────────────────────────────────────────

# Injected into every LLM call for a V3 session (editable per session in UI).
CROSS_MODULE_SYSTEM_PROMPT = (
    "Always reference insights from previous modules where relevant. "
    "Avoid contradictions with earlier findings. "
    "Build cumulative insights — each module should deepen the overall picture. "
    "Highlight confirmations or conflicts between modules explicitly.\n\n"
    "TABLES: When presenting comparative or quantitative data, always use Markdown table syntax "
    "(| col | col | with a |---|---| separator row). Tables will be rendered as styled HTML — "
    "do not use ASCII art or plain-text column alignment.\n\n"
    "VISUAL CONTENT: When your research identifies specific visual content that would "
    "meaningfully strengthen the report — such as a competitor's landing page, an ad creative, "
    "or a chart that is better seen than described — embed a visual marker on its own line:\n"
    "  [SCREENSHOT: https://full-url-here.com | Brief caption describing what this shows]\n"
    "  [GENERATE IMAGE: Detailed description of chart or diagram to generate | Caption]\n"
    "Use visuals sparingly and only when they genuinely add value that text cannot provide. "
    "Always include the caption after the | separator."
)

# The section library. Each entry is the default template; users can enable/disable
# sections and edit prompts before starting a session.
# locked=True sections cannot be unchecked in the UI.
SECTION_LIBRARY = [
    {
        "id": "market_regulation",
        "name": "Market & Regulation",
        "required_items": [
            "TAM figure (USD)",
            "SAM figure (USD)",
            "SOM estimate (USD)",
            "CAGR with source year",
            "At least 5 key trends",
            "Regulatory framework analysis",
        ],
        "expected_outputs": ["Market size table", "Trends summary", "Regulatory insight"],
        "default_prompt": (
            "Conduct a quantitative and strategic analysis of the market relevant to the research topic.\n\n"
            "Requirements:\n"
            "- Estimate TAM, SAM, SOM with clear assumptions\n"
            "- Segment by SMB, Enterprise, Public Sector where applicable\n"
            "- Analyse relevant regulation and compliance frameworks\n"
            "- Identify at least 5 key market trends\n\n"
            "Mandatory:\n"
            "- Must include structured tables and quantitative assumptions\n"
            "- Every figure must include an inline citation: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Market Size & TAM/SAM/SOM\n"
            "## Market Segmentation\n"
            "## Regulatory Landscape\n"
            "## Key Market Trends"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "competitor_deep_dive",
        "name": "Competitor Deep Dive",
        "required_items": [
            "At least 5 named competitors",
            "Business model per competitor",
            "Pricing tiers per competitor",
            "Strengths and weaknesses per competitor",
            "Competitor comparison table",
        ],
        "expected_outputs": ["Competitor comparison table", "SWOT per competitor"],
        "default_prompt": (
            "Analyse the top 5 competitors in the market.\n\n"
            "Requirements:\n"
            "- Business model\n"
            "- Target segments\n"
            "- Pricing tiers\n"
            "- Strengths/weaknesses\n"
            "- Positioning\n\n"
            "Mandatory:\n"
            "- Must include a comparison table\n"
            "- Every claim must include an inline citation: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Competitor Overview\n"
            "## Competitor Comparison Table\n"
            "## SWOT Analysis per Competitor\n"
            "## Competitive Positioning Map"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "pricing_business_model",
        "name": "Pricing & Business Model",
        "required_items": [
            "Pricing tier breakdown",
            "Revenue model description",
            "LTV estimate with assumptions",
            "CAC estimate with assumptions",
            "Churn rate assumptions",
        ],
        "expected_outputs": ["Pricing table", "LTV/CAC model"],
        "default_prompt": (
            "Analyse pricing strategies and revenue models in this market.\n\n"
            "Requirements:\n"
            "- Pricing tiers and structures used by market players\n"
            "- Upsell and expansion revenue patterns\n"
            "- LTV and churn assumptions\n"
            "- CAC benchmarks\n\n"
            "Mandatory:\n"
            "- Must include numeric assumptions\n"
            "- Every figure must include an inline citation: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Pricing Structures & Tiers\n"
            "## Revenue Model Analysis\n"
            "## LTV / CAC Model\n"
            "## Monetisation Opportunities"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "ppc_search_economics",
        "name": "PPC & Search Economics",
        "required_items": [
            "Target keyword list (min 10 keywords)",
            "CPC estimates per keyword",
            "CTR and CVR benchmarks",
            "CPL estimate",
            "CAC estimate from paid channel",
        ],
        "expected_outputs": ["Keyword table", "Funnel economics model"],
        "default_prompt": (
            "Analyse search demand and paid acquisition economics for this market.\n\n"
            "Requirements:\n"
            "- Target keywords (include multiple languages if relevant)\n"
            "- CPC and search intent per keyword\n"
            "- Estimate CTR, CVR, CPL, and CAC from paid search\n\n"
            "Mandatory:\n"
            "- Must include a full funnel numeric model\n"
            "- Every figure must include an inline citation: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Keyword Landscape\n"
            "## CPC & Intent Analysis\n"
            "## Funnel Economics Model\n"
            "## Paid Acquisition Strategy"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "funnels_landing_pages",
        "name": "Funnels & Landing Pages",
        "required_items": [
            "At least 3 competitors analysed",
            "Hero section breakdown per competitor",
            "CTA structure analysis",
            "Funnel flow description",
            "UX friction points identified",
        ],
        "expected_outputs": ["Funnel comparison table", "UX insights"],
        "default_prompt": (
            "Perform a deep funnel analysis of at least 3 competitors.\n\n"
            "Requirements:\n"
            "- Hero section and value proposition\n"
            "- CTA structure and placement\n"
            "- Funnel flow from ad to conversion\n"
            "- Trust signals\n"
            "- UX friction points\n\n"
            "Mandatory:\n"
            "- Must include step-by-step breakdown per competitor\n"
            "- Every observation must reference a specific competitor: [Source: CompanyName]\n\n"
            "Output:\n"
            "## Landing Page Analysis\n"
            "## Funnel Flow Comparison\n"
            "## Trust Signals & Social Proof\n"
            "## UX Friction & Opportunities"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "creative_messaging",
        "name": "Creative & Messaging",
        "required_items": [
            "Real ad creative examples from at least 2 platforms",
            "Headline analysis",
            "CTA patterns",
            "Messaging category classification",
            "Winning hooks identified",
        ],
        "expected_outputs": ["Creative table", "Messaging patterns", "Winning hooks", "Opportunity gaps"],
        "default_prompt": (
            "Conduct a full creative and messaging audit across platforms.\n\n"
            "Requirements:\n"
            "- Collect real creative examples from: Google Display, Mobile, Meta, YouTube\n"
            "- Analyse headlines, CTAs, visuals, and tone\n"
            "- Categorise messaging themes (e.g. fear, performance, inclusion, ROI)\n\n"
            "Mandatory:\n"
            "- No analysis without real creative examples — cite each creative with [Source: Platform, Brand]\n"
            "- Must include messaging pattern analysis\n\n"
            "Output:\n"
            "## Creative Audit by Platform\n"
            "## Messaging Patterns & Themes\n"
            "## Winning Hooks\n"
            "## Creative Opportunity Gaps"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "product_technology",
        "name": "Product & Technology",
        "required_items": [
            "Technology approach comparison (e.g. AI vs rule-based vs overlay)",
            "Automation depth assessment",
            "Key UX features listed",
            "Technology comparison table",
        ],
        "expected_outputs": ["Technology comparison", "Differentiation insight"],
        "default_prompt": (
            "Evaluate product capabilities and technology approaches in this market.\n\n"
            "Requirements:\n"
            "- Technology architecture (AI, automation depth, overlays, native)\n"
            "- Feature comparison across competitors\n"
            "- UX and product design quality\n\n"
            "Mandatory:\n"
            "- Must include a technology comparison table\n"
            "- Every claim must include an inline citation: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Technology Landscape\n"
            "## Product Feature Comparison\n"
            "## AI & Automation Assessment\n"
            "## Differentiation Opportunities"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "strategy_layer",
        "name": "Strategy Layer",
        "required_items": [
            "Unique Selling Proposition (USP) defined",
            "Positioning statement",
            "GTM channel plan",
            "Messaging per persona (min 2 personas)",
        ],
        "expected_outputs": ["USP", "Positioning", "Channel plan", "Messaging table"],
        "default_prompt": (
            "Synthesise findings into actionable go-to-market strategy.\n\n"
            "Requirements:\n"
            "- Define a clear USP based on competitive gaps\n"
            "- Write a positioning statement\n"
            "- Map GTM channels with priority\n"
            "- Define messaging per target persona\n\n"
            "Mandatory:\n"
            "- Must be actionable with specific recommendations\n"
            "- Reference findings from earlier modules\n\n"
            "Output:\n"
            "## Unique Selling Proposition\n"
            "## Positioning Statement\n"
            "## GTM Channel Plan\n"
            "## Messaging per Persona"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "final_synthesis",
        "name": "Final Synthesis",
        "required_items": [
            "Top 5 strategic insights",
            "Top 3 market gaps",
            "USP definition",
            "Positioning vs competitors",
            "3 high-ROI GTM actions",
        ],
        "expected_outputs": [
            "Top 5 insights",
            "Top 3 market gaps",
            "USP",
            "Competitive positioning",
            "3 GTM actions",
        ],
        "default_prompt": (
            "Combine all research modules into a final strategic output.\n\n"
            "You have access to the full research from all previous modules. Synthesise:\n"
            "- Top 5 cross-cutting strategic insights (with specific data)\n"
            "- Top 3 market gaps or underserved opportunities\n"
            "- Final USP definition\n"
            "- Positioning vs the main competitors\n"
            "- 3 highest-ROI GTM actions with rationale\n\n"
            "Mandatory:\n"
            "- Every claim must be grounded in data from earlier modules\n"
            "- Be specific: names, figures, percentages\n\n"
            "Output:\n"
            "## Executive Overview\n"
            "## Top 5 Strategic Insights\n"
            "## Top 3 Market Gaps\n"
            "## USP & Positioning\n"
            "## 3 High-ROI GTM Actions"
        ),
        "default_enabled": True,
        "locked": True,  # always included, always runs last
    },
]

# Critic prompt for V3 section-level review.
# Checks: (a) all required_items present, (b) all quantitative claims have citations.
SECTION_CRITIC_SYSTEM = """You are a rigorous market research critic reviewing a single report section.

Your job is to check two things only:
1. COMPLETENESS — are all required items listed below present and substantively addressed?
2. CITATIONS — does every quantitative claim (figures, percentages, market sizes, CPC values, etc.) have an inline citation in the format [Source: Name, Year]?

Output ONLY valid JSON (no markdown, no code fences):
{
  "verdict": "PASS" or "REVISE",
  "missing_items": ["item description if missing, else empty list"],
  "uncited_claims": ["quote the uncited claim if any, else empty list"],
  "gaps_summary": "one sentence describing what must be improved, or empty string if PASS"
}

Be strict: PASS only if ALL required items are addressed AND all quantitative claims are cited."""

# System prompt for building a 2-sentence section summary (used for reference context).
SECTION_SUMMARY_SYSTEM = (
    "You are a research editor. Write exactly 2 sentences summarising the key findings "
    "of the section provided. Be specific: include the most important figure or named entity. "
    "Output only the 2-sentence summary — no preamble."
)
