"""
Market Research product and sector registry.

Two-level config hierarchy:  Product → Sector → Section Library

PRODUCTS   — top-level product definitions (currently just market_research).
             Future non-research products will be added here.

SECTORS    — one entry per research type.  Each sector carries:
               display_name         shown in UI
               description          one-line description for the sector picker
               section_library      list[dict] — same schema as SECTION_LIBRARY
               default_system_prompt session-level cross-module instruction
               terminology_overrides optional rename map (unused today, reserved)

config.py re-exports SECTION_LIBRARY from the business_intelligence sector for
backwards compatibility.  All pipeline code should import from config.py or here.
"""

# No imports from config.py — registry is the source of truth.
# config.py imports from here for backwards compatibility.

# ── Product registry ──────────────────────────────────────────────────────────

PRODUCTS: dict[str, dict] = {
    "market_research": {
        "display_name": "Market Research",
        "description": "Multi-LLM, section-based market intelligence reports",
        "sectors": [
            "business_intelligence",
            "academic",
            "vc_due_diligence",
            "product_discovery",
        ],
        "default_sector": "business_intelligence",
    },
}

# ── Sector: Business Intelligence (current default) ───────────────────────────

_BI_SYSTEM_PROMPT = (
    "Always reference insights from previous modules where relevant. "
    "Avoid contradictions with earlier findings. "
    "Build cumulative insights — each module should deepen the overall picture. "
    "Highlight confirmations or conflicts between modules explicitly.\n\n"
    "TABLES: When presenting comparative or quantitative data, always use Markdown table syntax "
    "(| col | col | with a |---|---| separator row). Tables will be rendered as styled HTML — "
    "do not use ASCII art or plain-text column alignment.\n\n"
    "VISUAL CONTENT: You MUST embed visual markers for any content that is better seen than "
    "described. This is not optional — failure to embed markers means no images appear in the "
    "final report. Use these two formats (embed directly in the text, on their own line):\n"
    "  [SCREENSHOT: https://full-url-here.com | Brief caption]\n"
    "    — Use for publicly accessible web pages (landing pages, pricing pages, product pages).\n"
    "      Do NOT use for pages that require login (ad libraries, dashboards, gated tools).\n"
    "  [GENERATE IMAGE: Detailed visual description 40-60 words | Caption]\n"
    "    — Use for ad creative recreations, charts, diagrams, comparison matrices, or any URL "
    "that requires authentication. Describe the visual in enough detail that an AI image "
    "generator can faithfully recreate it: layout, colors, key text, format, style.\n"
    "Always include the | separator and caption. Aim for 1-3 visuals per section where relevant."
)

_BI_SECTION_LIBRARY = [
    {
        "id": "executive_summary",
        "name": "Executive Summary",
        "required_items": [
            "Main market opportunities",
            "Key challenges and risks",
            "Strategic recommendations",
            "Pros and cons summary",
        ],
        "expected_outputs": ["Opportunities", "Challenges", "Recommendations", "Pros/Cons"],
        "default_prompt": (
            "Synthesise the key takeaways from all research sections into a concise executive summary.\n\n"
            "Requirements:\n"
            "- Maximum 3 pages (~800-1200 words)\n"
            "- Cover the main opportunities, challenges, risks, and strategic recommendations\n"
            "- Be selective: include only the most decision-relevant insights\n"
            "- Use clear sections:\n"
            "  ## Market Overview\n"
            "  ## Key Opportunities\n"
            "  ## Key Challenges & Risks\n"
            "  ## Pros and Cons\n"
            "  ## Strategic Recommendations\n"
            "- Be specific: include key figures and named entities from the research\n\n"
            "This section is synthesised from all other research sections. "
            "Do not add new research — draw only from what the research established."
        ),
        "default_enabled": True,
        "locked": True,
    },
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
            "- Every observation must reference a specific competitor: [Source: CompanyName]\n"
            "- For each competitor's landing page, embed a [SCREENSHOT: url | caption] marker "
            "using the real homepage or pricing page URL. Only use SCREENSHOT for pages that are "
            "publicly accessible without login. If a page requires auth, use "
            "[GENERATE IMAGE: description | caption] instead.\n\n"
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
            "- Must include messaging pattern analysis\n"
            "- For EACH creative example you describe, you MUST embed a [GENERATE IMAGE:] marker "
            "immediately after the example heading. Describe the ad creative in 40-60 words: "
            "the format (static/video/carousel), key visuals, layout, color palette, headline "
            "text visible, and any UI elements shown. Example:\n"
            "  [GENERATE IMAGE: Static Facebook ad. Clean product screenshot of a text-based "
            "video editor on a MacBook, teal accent palette, bold headline 'Edit video by editing "
            "text. Yes, really.' in white sans-serif, Try Free CTA button bottom-right. "
            "Professional SaaS aesthetic. | Descript Meta ad — text-based editor UI]\n\n"
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
            "Technology approach comparison",
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
        "locked": True,
    },
]

# ── Sector: Academic & Research Assistant ─────────────────────────────────────

_ACADEMIC_SYSTEM_PROMPT = (
    "You are conducting academic research. Use objective, scholarly language. "
    "Every factual claim must be attributed to a specific source. "
    "Build cumulative insights across sections — later sections should reference and extend earlier findings. "
    "Avoid repetition; note when prior sections have already covered a concept.\n\n"
    "TABLES: Use Markdown table syntax (| col | col | with |---|---| separator row) for comparative data.\n"
    "CITATIONS: Every quantitative or factual claim must include [Source: Author, Year] inline."
)

_ACADEMIC_SECTION_LIBRARY = [
    {
        "id": "executive_abstract",
        "name": "Executive Abstract",
        "required_items": [
            "Research question or thesis",
            "Key findings summary",
            "Methodology overview",
            "Identified research gaps",
            "Recommendations for further study",
        ],
        "expected_outputs": ["Abstract", "Key findings", "Research gaps", "Further study directions"],
        "default_prompt": (
            "Write a concise Executive Abstract synthesising the full research.\n\n"
            "Requirements:\n"
            "- Clearly state the research question or thesis\n"
            "- Summarise the most significant findings from each section\n"
            "- Note the key research gaps identified\n"
            "- Suggest 2-3 directions for further study\n"
            "- Maximum 600-800 words\n\n"
            "Output:\n"
            "## Research Question\n"
            "## Key Findings\n"
            "## Research Gaps\n"
            "## Directions for Further Study"
        ),
        "default_enabled": True,
        "locked": True,
    },
    {
        "id": "literature_landscape",
        "name": "Literature Landscape",
        "required_items": [
            "At least 10 cited works",
            "Major theoretical frameworks identified",
            "Key journals and publication venues",
            "Historical development of the field",
            "Current state of knowledge",
        ],
        "expected_outputs": ["Literature map", "Framework overview", "Chronological development"],
        "default_prompt": (
            "Survey the existing literature on the research topic.\n\n"
            "Requirements:\n"
            "- Map the major bodies of work and theoretical traditions\n"
            "- Trace the historical development of the field\n"
            "- Identify the most influential works and why they matter\n"
            "- Note key publication venues (journals, conferences)\n"
            "- Every cited work must include [Source: Author, Year]\n\n"
            "Output:\n"
            "## Historical Development\n"
            "## Major Theoretical Frameworks\n"
            "## Landmark Works & Authors\n"
            "## Key Publication Venues"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "research_gap_analysis",
        "name": "Research Gap Analysis",
        "required_items": [
            "At least 3 clearly defined research gaps",
            "Evidence for each gap from the literature",
            "Ranking of gaps by significance",
            "Unexplored methodologies identified",
        ],
        "expected_outputs": ["Gap matrix", "Gap significance ranking", "Methodology opportunities"],
        "default_prompt": (
            "Identify what is missing or understudied in the existing literature.\n\n"
            "Requirements:\n"
            "- Define each gap clearly: what is known vs what is not\n"
            "- Cite evidence that the gap exists (references calling for further work)\n"
            "- Rank gaps by research significance and feasibility\n"
            "- Identify methodological approaches not yet applied to the topic\n"
            "- Every gap must reference at least one source: [Source: Author, Year]\n\n"
            "Output:\n"
            "## Identified Research Gaps\n"
            "## Gap Significance Matrix\n"
            "## Methodological Opportunities\n"
            "## Most Promising Directions"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "key_scholars_citations",
        "name": "Key Scholars & Citations",
        "required_items": [
            "At least 5 key scholars profiled",
            "Seminal papers identified",
            "Citation networks described",
            "Conflicting schools of thought mapped",
        ],
        "expected_outputs": ["Scholar profiles", "Seminal papers list", "Citation network map"],
        "default_prompt": (
            "Map the key scholars, seminal papers, and citation networks in this field.\n\n"
            "Requirements:\n"
            "- Profile the 5 most influential scholars and their contributions\n"
            "- Identify the 5-10 most-cited papers and why they are foundational\n"
            "- Describe the citation network: who cites whom, which camps exist\n"
            "- Note competing schools of thought and their core disagreements\n"
            "- All references in [Source: Author, Year] format\n\n"
            "Output:\n"
            "## Key Scholars\n"
            "## Seminal Papers\n"
            "## Citation Networks\n"
            "## Competing Schools of Thought"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "thematic_mapping",
        "name": "Thematic Mapping",
        "required_items": [
            "At least 4 major themes identified",
            "Theme definitions with evidence",
            "Connections between themes described",
            "Qualitative vs quantitative split noted",
        ],
        "expected_outputs": ["Theme definitions", "Theme relationship map", "Methodology split analysis"],
        "default_prompt": (
            "Identify and map the major themes and theoretical constructs in the literature.\n\n"
            "Requirements:\n"
            "- Define each theme precisely with supporting citations\n"
            "- Describe how themes interrelate (complementary, competing, hierarchical)\n"
            "- Note whether each theme is predominantly studied qualitatively or quantitatively\n"
            "- Identify under-theorised areas within each theme\n"
            "- All claims cited: [Source: Author, Year]\n\n"
            "Output:\n"
            "## Major Themes\n"
            "## Theme Relationships\n"
            "## Qualitative vs Quantitative Split\n"
            "## Under-Theorised Areas"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "methodology_framework",
        "name": "Methodology & Framework Suggestions",
        "required_items": [
            "Overview of methods used in the field",
            "Strengths and limitations per method",
            "Recommended methodology for filling identified gaps",
            "Ethical considerations",
        ],
        "expected_outputs": ["Methods comparison", "Recommended approach", "Ethics checklist"],
        "default_prompt": (
            "Evaluate methodological approaches used in the field and recommend a framework.\n\n"
            "Requirements:\n"
            "- Survey the research methods used across the literature\n"
            "- Assess strengths and limitations of each method\n"
            "- Recommend a methodology suited to filling the identified research gaps\n"
            "- Identify ethical considerations relevant to the topic\n"
            "- All comparative claims cited: [Source: Author, Year]\n\n"
            "Output:\n"
            "## Methods in the Field\n"
            "## Strengths & Limitations\n"
            "## Recommended Framework\n"
            "## Ethical Considerations"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "research_design_blueprint",
        "name": "Research Design Blueprint",
        "required_items": [
            "Research questions or hypotheses",
            "Proposed methodology",
            "Data collection strategy",
            "Analysis approach",
            "Limitations and mitigations",
        ],
        "expected_outputs": ["Research questions", "Methodology outline", "Data plan", "Limitations"],
        "default_prompt": (
            "Outline a concrete research design for studying this topic.\n\n"
            "Requirements:\n"
            "- Formulate 2-3 specific, testable research questions or hypotheses\n"
            "- Specify the research methodology (quantitative/qualitative/mixed)\n"
            "- Describe the data collection strategy (sources, instruments, sample)\n"
            "- Outline the analysis approach\n"
            "- Identify limitations and propose mitigations\n\n"
            "Output:\n"
            "## Research Questions / Hypotheses\n"
            "## Methodology\n"
            "## Data Collection Strategy\n"
            "## Analysis Approach\n"
            "## Limitations & Mitigations"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "bibliography_appendix",
        "name": "Bibliography Appendix",
        "required_items": [
            "All sources cited across sections listed",
            "APA format used",
            "Annotated where significant",
        ],
        "expected_outputs": ["Full bibliography", "Annotated entries"],
        "default_prompt": (
            "Compile a full bibliography from all sources cited in this research.\n\n"
            "Requirements:\n"
            "- List every source cited across all sections\n"
            "- Format in APA style: Author, A. B. (Year). Title. Journal/Publisher.\n"
            "- Add a one-sentence annotation for the 5-10 most significant works\n"
            "- Group by: Foundational Works / Empirical Studies / Reviews & Meta-analyses\n\n"
            "Output:\n"
            "## Foundational Works\n"
            "## Empirical Studies\n"
            "## Reviews & Meta-analyses\n"
            "## Annotated Bibliography"
        ),
        "default_enabled": True,
        "locked": False,
    },
]

# ── Sector: VC & Investor Due Diligence ──────────────────────────────────────

_VC_SYSTEM_PROMPT = (
    "You are conducting investor due diligence. Be objective and risk-aware. "
    "Every financial figure must be cited or explicitly stated as an estimate with assumptions. "
    "Build a coherent investment picture across sections — note corroborating and conflicting signals. "
    "Avoid hype; present balanced risk/reward assessments.\n\n"
    "TABLES: Use Markdown table syntax for all comparative data.\n"
    "CITATIONS: Every quantitative claim must include [Source: Name, Year] inline."
)

_VC_SECTION_LIBRARY = [
    {
        "id": "executive_investment_memo",
        "name": "Executive Investment Memo",
        "required_items": [
            "Investment thesis in one paragraph",
            "Key strengths and risks",
            "Investment readiness verdict",
            "Critical next steps before investment",
        ],
        "expected_outputs": ["Investment thesis", "Risk/reward summary", "Verdict", "Next steps"],
        "default_prompt": (
            "Write a concise Executive Investment Memo synthesising all due diligence findings.\n\n"
            "Requirements:\n"
            "- State the investment thesis in one clear paragraph\n"
            "- Summarise the 3 strongest signals and 3 most significant risks\n"
            "- Give an investment readiness verdict: Strong / Conditional / Not Ready\n"
            "- List the 3 critical items that must be validated before investing\n"
            "- Maximum 800 words\n\n"
            "Output:\n"
            "## Investment Thesis\n"
            "## Strengths & Risks Summary\n"
            "## Investment Readiness Verdict\n"
            "## Critical Next Steps"
        ),
        "default_enabled": True,
        "locked": True,
    },
    {
        "id": "market_sizing_vc",
        "name": "Market Sizing (TAM/SAM/SOM)",
        "required_items": [
            "TAM figure with methodology",
            "SAM figure with rationale",
            "SOM estimate with growth assumptions",
            "Market growth rate (CAGR)",
            "Key market drivers identified",
        ],
        "expected_outputs": ["Market size table", "Sizing methodology", "Growth drivers"],
        "default_prompt": (
            "Conduct rigorous market sizing analysis for investor evaluation.\n\n"
            "Requirements:\n"
            "- Calculate TAM using both top-down and bottom-up approaches\n"
            "- Define SAM with clear segmentation rationale\n"
            "- Estimate SOM with realistic capture assumptions\n"
            "- Provide CAGR with source\n"
            "- Identify the 3-5 primary market growth drivers\n"
            "- Every figure must include [Source: Name, Year]\n\n"
            "Output:\n"
            "## TAM / SAM / SOM\n"
            "## Sizing Methodology\n"
            "## Market Growth Rate\n"
            "## Key Market Drivers"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "competitive_moat",
        "name": "Competitive Moat Analysis",
        "required_items": [
            "At least 5 competitors identified",
            "Moat types assessed (network, IP, switching cost, scale, brand)",
            "Defensibility rating",
            "Moat durability assessment",
        ],
        "expected_outputs": ["Competitor table", "Moat assessment", "Defensibility score"],
        "default_prompt": (
            "Assess the competitive landscape and defensibility of this venture.\n\n"
            "Requirements:\n"
            "- Map the top 5 competitors with positioning and funding\n"
            "- Assess moat types: network effects, IP/patents, switching costs, scale, brand\n"
            "- Rate defensibility (Strong/Moderate/Weak) with rationale\n"
            "- Assess moat durability over 3-5 years\n"
            "- Identify the most credible competitive threats\n"
            "- All claims cited: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Competitive Landscape\n"
            "## Moat Assessment\n"
            "## Defensibility Rating\n"
            "## Competitive Threats"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "team_founder_assessment",
        "name": "Team & Founder Assessment",
        "required_items": [
            "Founder backgrounds and domain expertise",
            "Prior startup experience",
            "Team completeness assessment",
            "Key hires needed",
        ],
        "expected_outputs": ["Founder profiles", "Team gaps", "Domain expertise rating"],
        "default_prompt": (
            "Evaluate the founding team and leadership against investor standards.\n\n"
            "Requirements:\n"
            "- Profile each founder: background, relevant domain expertise, past exits/roles\n"
            "- Assess team completeness: which C-suite roles are covered\n"
            "- Identify critical missing roles (e.g. CTO, CMO, domain expert)\n"
            "- Evaluate founder-market fit: do they have an unfair advantage in this space?\n"
            "- Note any red flags (frequent pivots, gaps in history, conflicting roles)\n\n"
            "Output:\n"
            "## Founder Profiles\n"
            "## Team Completeness\n"
            "## Critical Gaps\n"
            "## Founder-Market Fit Assessment"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "regulatory_legal_risk",
        "name": "Regulatory & Legal Risk",
        "required_items": [
            "Applicable regulatory frameworks identified",
            "Current compliance status",
            "Pending or likely regulatory changes",
            "Legal risk rating",
        ],
        "expected_outputs": ["Regulatory map", "Compliance checklist", "Legal risk rating"],
        "default_prompt": (
            "Assess regulatory exposure and legal risk for this venture.\n\n"
            "Requirements:\n"
            "- Identify all applicable regulatory frameworks (by jurisdiction)\n"
            "- Assess current compliance status\n"
            "- Evaluate pending or anticipated regulatory changes and their impact\n"
            "- Rate overall legal risk (High/Medium/Low) with rationale\n"
            "- Note any IP, data privacy, or licensing risks\n"
            "- All regulatory claims cited: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Regulatory Framework\n"
            "## Compliance Status\n"
            "## Regulatory Change Risk\n"
            "## Legal Risk Rating"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "financial_model_viability",
        "name": "Financial Model Viability",
        "required_items": [
            "Revenue model description",
            "Unit economics (LTV, CAC, payback period)",
            "Burn rate and runway estimate",
            "Path to profitability outlined",
            "Key financial assumptions stated",
        ],
        "expected_outputs": ["Unit economics table", "Runway analysis", "Profitability path"],
        "default_prompt": (
            "Evaluate the financial model and unit economics for investor scrutiny.\n\n"
            "Requirements:\n"
            "- Describe the revenue model and monetisation mechanism\n"
            "- Calculate or estimate: LTV, CAC, LTV:CAC ratio, payback period\n"
            "- Estimate burn rate and runway given typical seed/Series A raise sizes\n"
            "- Outline the path to profitability with key milestones\n"
            "- State all assumptions explicitly\n"
            "- Every benchmark cited: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Revenue Model\n"
            "## Unit Economics\n"
            "## Burn & Runway\n"
            "## Path to Profitability"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "exit_landscape",
        "name": "Exit Landscape",
        "required_items": [
            "M&A comparables (at least 3)",
            "Strategic acquirers identified",
            "IPO readiness assessment",
            "Expected exit multiples",
        ],
        "expected_outputs": ["M&A comps table", "Strategic buyer map", "Exit multiple range"],
        "default_prompt": (
            "Analyse the exit landscape for this venture.\n\n"
            "Requirements:\n"
            "- Identify 3-5 M&A comparable transactions with deal size and rationale\n"
            "- Map strategic acquirers who would benefit from acquiring this company\n"
            "- Assess IPO readiness: ARR needed, market conditions, comparable public comps\n"
            "- Estimate exit multiples (Revenue, EBITDA) based on sector benchmarks\n"
            "- All transactions and multiples cited: [Source: Name, Year]\n\n"
            "Output:\n"
            "## M&A Comparables\n"
            "## Strategic Acquirers\n"
            "## IPO Readiness\n"
            "## Exit Multiple Range"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "investment_readiness_score",
        "name": "Investment Readiness Score",
        "required_items": [
            "Scores across 5+ dimensions",
            "Overall readiness rating",
            "Top 3 risk factors",
            "Top 3 investment catalysts",
        ],
        "expected_outputs": ["Scorecard table", "Overall rating", "Risk/catalyst summary"],
        "default_prompt": (
            "Score this venture's investment readiness across key dimensions.\n\n"
            "Requirements:\n"
            "- Score each dimension 1-10 with brief rationale:\n"
            "  Market Opportunity, Team, Product/Technology, Business Model, Competitive Moat, Traction\n"
            "- Calculate overall weighted score\n"
            "- List the top 3 risk factors that could undermine the investment\n"
            "- List the top 3 catalysts that would accelerate value creation\n"
            "- Base all scores on findings from prior sections\n\n"
            "Output:\n"
            "## Investment Readiness Scorecard\n"
            "## Overall Rating\n"
            "## Top 3 Risk Factors\n"
            "## Top 3 Investment Catalysts"
        ),
        "default_enabled": True,
        "locked": False,
    },
]

# ── Sector: Product Management Discovery ─────────────────────────────────────

_PM_SYSTEM_PROMPT = (
    "You are conducting product discovery research. Be user-centric and evidence-based. "
    "Ground every recommendation in user research signals or competitive evidence. "
    "Build cumulative product intelligence across sections — connect user pain points to feature decisions. "
    "Use precise product terminology (ICP, jobs-to-be-done, MVP, GTM, NPS, DAU/MAU).\n\n"
    "TABLES: Use Markdown table syntax for all feature matrices and comparisons.\n"
    "CITATIONS: Every competitive or market claim must include [Source: Name, Year] inline."
)

_PM_SECTION_LIBRARY = [
    {
        "id": "product_executive_summary",
        "name": "Product Executive Summary",
        "required_items": [
            "Problem statement",
            "Proposed solution overview",
            "Target user segment",
            "Key differentiators",
            "Recommended next steps",
        ],
        "expected_outputs": ["Problem/solution summary", "User segment", "Differentiators", "Next steps"],
        "default_prompt": (
            "Write a Product Executive Summary synthesising all discovery findings.\n\n"
            "Requirements:\n"
            "- State the validated problem and proposed solution clearly\n"
            "- Define the primary target user segment\n"
            "- Summarise the 3 key differentiators vs existing solutions\n"
            "- Recommend the 3 highest-priority next steps\n"
            "- Maximum 600-800 words\n\n"
            "Output:\n"
            "## Problem & Solution\n"
            "## Target User Segment\n"
            "## Key Differentiators\n"
            "## Recommended Next Steps"
        ),
        "default_enabled": True,
        "locked": True,
    },
    {
        "id": "user_persona_deep_dive",
        "name": "User Persona Deep Dive",
        "required_items": [
            "At least 2 detailed personas",
            "Jobs-to-be-done per persona",
            "Pain points and motivations",
            "Current solutions and frustrations",
            "Willingness to pay signal",
        ],
        "expected_outputs": ["Persona cards", "JTBD map", "Pain/motivation matrix"],
        "default_prompt": (
            "Build detailed user personas grounded in research signals.\n\n"
            "Requirements:\n"
            "- Define 2-3 distinct personas with demographics, roles, context\n"
            "- Map jobs-to-be-done for each persona (functional, social, emotional)\n"
            "- Identify top 3 pain points and motivations per persona\n"
            "- Describe current solutions they use and what frustrates them\n"
            "- Include willingness-to-pay signal (price sensitivity, budget context)\n"
            "- Cite any research, forum posts, reviews, or surveys: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Persona Profiles\n"
            "## Jobs-to-be-Done\n"
            "## Pain Points & Motivations\n"
            "## Current Solutions & Frustrations"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "problem_statement_validation",
        "name": "Problem Statement Validation",
        "required_items": [
            "Problem statement clearly defined",
            "Evidence of problem existence",
            "Problem frequency and severity assessed",
            "Who experiences it and when",
        ],
        "expected_outputs": ["Problem statement", "Evidence matrix", "Severity assessment"],
        "default_prompt": (
            "Validate and sharpen the core problem statement.\n\n"
            "Requirements:\n"
            "- State the problem precisely in one paragraph\n"
            "- Provide evidence it exists (forum posts, reviews, research, user quotes)\n"
            "- Assess frequency (how often) and severity (how painful)\n"
            "- Define who experiences it most acutely and in what context\n"
            "- Distinguish must-have (hair on fire) from nice-to-have problems\n"
            "- All evidence cited: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Problem Statement\n"
            "## Evidence of Problem\n"
            "## Frequency & Severity\n"
            "## Primary Sufferers"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "feature_matrix_mapping",
        "name": "Feature Matrix Mapping",
        "required_items": [
            "At least 5 competing products mapped",
            "Feature comparison table",
            "Feature gaps identified",
            "Differentiation opportunities",
        ],
        "expected_outputs": ["Feature matrix table", "Gap analysis", "Differentiation opportunities"],
        "default_prompt": (
            "Build a comprehensive feature matrix across competing products.\n\n"
            "Requirements:\n"
            "- Map 5+ competing products across 10+ features\n"
            "- Use a table: products as columns, features as rows, ✓/✗/Partial as values\n"
            "- Identify features no current product does well (gaps)\n"
            "- Identify features where differentiation is possible\n"
            "- Prioritise features by: user demand × competitive gap\n"
            "- All feature claims cited: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Feature Matrix Table\n"
            "## Feature Gaps\n"
            "## Differentiation Opportunities\n"
            "## Feature Priority Matrix"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "competitive_benchmarking",
        "name": "Competitive Benchmarking",
        "required_items": [
            "At least 3 products benchmarked",
            "UX quality assessment",
            "Pricing comparison",
            "User satisfaction signals (reviews, NPS)",
        ],
        "expected_outputs": ["Benchmark table", "UX quality ratings", "Pricing comparison"],
        "default_prompt": (
            "Benchmark competing products on quality, pricing, and user satisfaction.\n\n"
            "Requirements:\n"
            "- Evaluate 3-5 products across: UX quality, onboarding, performance, support\n"
            "- Compare pricing models and tiers\n"
            "- Gather user satisfaction signals (App Store reviews, G2, Trustpilot, NPS)\n"
            "- Identify where existing products consistently disappoint users\n"
            "- All claims cited: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Product Quality Benchmarks\n"
            "## Pricing Comparison\n"
            "## User Satisfaction Signals\n"
            "## Consistent Disappointment Points"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "gtm_product_alignment",
        "name": "GTM & Product Alignment",
        "required_items": [
            "Recommended distribution channels",
            "Pricing strategy recommendation",
            "Packaging recommendation",
            "Launch sequencing",
        ],
        "expected_outputs": ["Channel strategy", "Pricing model", "Packaging options", "Launch plan"],
        "default_prompt": (
            "Define the go-to-market strategy aligned to the product and personas.\n\n"
            "Requirements:\n"
            "- Recommend distribution channels ranked by fit for target personas\n"
            "- Propose a pricing model (freemium, per-seat, usage, flat-rate) with rationale\n"
            "- Define packaging tiers (Starter / Pro / Enterprise) with included features\n"
            "- Recommend launch sequencing: who to target first, why, with what messaging\n"
            "- All benchmarks cited: [Source: Name, Year]\n\n"
            "Output:\n"
            "## Distribution Channels\n"
            "## Pricing Strategy\n"
            "## Product Packaging\n"
            "## Launch Sequencing"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "technical_feasibility",
        "name": "Technical Feasibility",
        "required_items": [
            "Core technical components identified",
            "Build complexity rated",
            "Key technology choices recommended",
            "Build vs buy assessment",
        ],
        "expected_outputs": ["Tech stack recommendation", "Complexity rating", "Build/buy decisions"],
        "default_prompt": (
            "Evaluate technical feasibility and recommend an architecture approach.\n\n"
            "Requirements:\n"
            "- Identify the core technical components needed\n"
            "- Rate overall build complexity (Low/Medium/High) with rationale\n"
            "- Recommend key technology choices (language, framework, infra)\n"
            "- Assess build vs buy for each major component\n"
            "- Identify the highest-risk technical challenges\n\n"
            "Output:\n"
            "## Core Technical Components\n"
            "## Complexity Assessment\n"
            "## Technology Recommendations\n"
            "## Build vs Buy Decisions\n"
            "## Highest-Risk Technical Challenges"
        ),
        "default_enabled": True,
        "locked": False,
    },
    {
        "id": "prd_blueprint",
        "name": "PRD Blueprint",
        "required_items": [
            "Problem and goals stated",
            "User stories for core flows",
            "MVP scope defined",
            "Success metrics defined",
            "Out of scope items listed",
        ],
        "expected_outputs": ["PRD document", "User stories", "MVP scope", "Success metrics"],
        "default_prompt": (
            "Write a Product Requirements Document (PRD) blueprint.\n\n"
            "Requirements:\n"
            "- State the problem this product solves and the desired outcome\n"
            "- Write user stories for the 3-5 core flows: As a [persona], I want [action] so that [outcome]\n"
            "- Define the MVP scope: what is in, what is explicitly out\n"
            "- Define success metrics (activation rate, retention, NPS, DAU, revenue)\n"
            "- List assumptions that must be validated\n\n"
            "Output:\n"
            "## Problem & Goals\n"
            "## Core User Stories\n"
            "## MVP Scope\n"
            "## Success Metrics\n"
            "## Out of Scope\n"
            "## Key Assumptions"
        ),
        "default_enabled": True,
        "locked": False,
    },
]

# ── Sectors dict ──────────────────────────────────────────────────────────────

SECTORS: dict[str, dict] = {
    "business_intelligence": {
        "display_name": "Business Intelligence",
        "description": "Market sizing, competitive analysis, pricing, acquisition economics, and GTM strategy",
        "section_library": _BI_SECTION_LIBRARY,
        "default_system_prompt": _BI_SYSTEM_PROMPT,  # same content as CROSS_MODULE_SYSTEM_PROMPT in config.py
        "terminology_overrides": {},
    },
    "academic": {
        "display_name": "Academic & Research",
        "description": "Literature review, gap analysis, methodology design, and bibliography",
        "section_library": _ACADEMIC_SECTION_LIBRARY,
        "default_system_prompt": _ACADEMIC_SYSTEM_PROMPT,
        "terminology_overrides": {
            "Final Synthesis": "Executive Abstract",
        },
    },
    "vc_due_diligence": {
        "display_name": "VC Due Diligence",
        "description": "Investment readiness assessment: market sizing, moat, financials, team, and exit landscape",
        "section_library": _VC_SECTION_LIBRARY,
        "default_system_prompt": _VC_SYSTEM_PROMPT,
        "terminology_overrides": {},
    },
    "product_discovery": {
        "display_name": "Product Discovery",
        "description": "User personas, problem validation, feature matrix, PRD blueprint, and GTM alignment",
        "section_library": _PM_SECTION_LIBRARY,
        "default_system_prompt": _PM_SYSTEM_PROMPT,
        "terminology_overrides": {},
    },
}

# ── Report configuration helpers ──────────────────────────────────────────────

# Token budget per output depth
DEPTH_MAX_TOKENS: dict[str, int] = {
    "executive":   4096,
    "standard":    8192,
    "exhaustive":  16384,
}

_DEPTH_DESCRIPTIONS: dict[str, str] = {
    "executive":   "EXECUTIVE SUMMARY DEPTH — focus on the most critical findings only; avoid lengthy elaboration; prioritise brevity and decision-relevance; target 1-2 pages per section",
    "standard":    "STANDARD DEPTH — comprehensive analysis with data and examples; normal section length",
    "exhaustive":  "EXHAUSTIVE / WHITEPAPER DEPTH — include raw data tables, full statistical breakdowns, cited primary sources for every claim, detailed methodology notes; target 30+ pages total",
}

_STYLE_DESCRIPTIONS: dict[str, str] = {
    "corporate":  "CORPORATE/CONSULTING STYLE — direct, action-oriented, professional tone; McKinsey-style language; active voice; bullet-point summaries; decisive recommendations",
    "academic":   "ACADEMIC STYLE — objective, formal register; passive voice where appropriate; hedging language ('the data suggests', 'evidence indicates', 'potentially'); avoid superlatives",
    "aggressive": "AGGRESSIVE/VENTURE STYLE — high-energy, growth-focused; emphasise disruption and opportunity; confident assertions; startup vernacular where appropriate",
}

_FRAMEWORK_DESCRIPTIONS: dict[str, str] = {
    "swot":        "Apply SWOT analysis (Strengths, Weaknesses, Opportunities, Threats) as the analytical lens wherever strategic assessment is required",
    "pestle":      "Apply PESTLE analysis (Political, Economic, Social, Technological, Legal, Environmental) as the analytical lens for market and environmental factors",
    "lean_canvas": "Apply Lean Canvas thinking: frame analysis around Problem, Solution, Unique Value Proposition, Unfair Advantage, Customer Segments, Key Metrics, Channels, Cost Structure, Revenue Streams",
    "porters":     "Apply Porter's Five Forces (Threat of New Entrants, Bargaining Power of Suppliers, Bargaining Power of Buyers, Threat of Substitutes, Competitive Rivalry) for competitive analysis",
    "none":        "",
}

_CITATION_DESCRIPTIONS: dict[str, str] = {
    "inline":    "Use inline citations in the format: [Source: Name, Year]",
    "apa":       "Use APA in-text citations: (Author, Year) after every factual claim; full references in bibliography",
    "mla":       "Use MLA in-text citations: (Author Page) after every factual claim; full Works Cited at the end",
    "hyperlink": "Use hyperlink citations: embed source URLs as [Source: Title](URL) after every factual claim",
}


def build_report_directives(report_config: dict) -> str:
    """
    Build the '## Report Directives' block injected into every section research prompt.
    Returns an empty string if report_config is falsy or contains only defaults.
    """
    if not report_config:
        return ""

    depth  = report_config.get("output_depth", "standard")
    style  = report_config.get("writing_style", "corporate")
    framework = report_config.get("framework", "none")
    citation  = report_config.get("citation_format", "inline")

    lines = ["\n\n## Report Directives"]
    lines.append(f"- Output depth: {_DEPTH_DESCRIPTIONS.get(depth, '')}")
    lines.append(f"- Writing style: {_STYLE_DESCRIPTIONS.get(style, '')}")
    if framework and framework != "none":
        lines.append(f"- Analytical framework: {_FRAMEWORK_DESCRIPTIONS.get(framework, '')}")
    lines.append(f"- Citation format: {_CITATION_DESCRIPTIONS.get(citation, _CITATION_DESCRIPTIONS['inline'])}")

    return "\n".join(lines)
