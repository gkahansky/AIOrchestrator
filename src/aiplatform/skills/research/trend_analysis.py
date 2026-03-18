"""
Skill: trend_analysis
Score and rank topics by demand using search volume and trend signals.

Status: Sprint 2 — not yet implemented.

Scoring model (from CLAUDE.md):
  Demand (40%)       — Google Trends 90-day growth + Etsy monthly search count
  Competition (35%)  — Inverse of listing count and top-seller review density
  Monetisation (25%) — Average sale price × estimated conversion rate

Themes scoring ≥ 60 proceed to Phase 2.
"""


def score_theme(theme: str, search_data: dict) -> dict:
    """
    Score a single theme against demand, competition, and monetisation signals.

    Returns:
        { theme, score, demand, competition, monetisation, proceed }
    """
    raise NotImplementedError("trend_analysis is a Sprint 2 feature.")


def rank_themes(themes: list[str], search_data: dict) -> list[dict]:
    """
    Score and rank a list of themes. Returns sorted by score descending.
    Filters to themes with score >= 60.
    """
    raise NotImplementedError("trend_analysis is a Sprint 2 feature.")
