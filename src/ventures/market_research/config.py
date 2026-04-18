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
