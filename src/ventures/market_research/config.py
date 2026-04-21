"""Market Research venture configuration."""

import os

DRIVE_FOLDER = os.environ.get("MARKET_RESEARCH_DRIVE_FOLDER", "Market Research Reports")

# Research angles assigned per LLM slot (rotates if fewer LLMs selected)
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
