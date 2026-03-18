"""
Skill: trend_analysis
Score and rank topics by demand, competition, and monetisation.
Venture-agnostic: works for any product category.

Scoring model (from CLAUDE.md):
  Demand (40%)       — Google Trends 90-day avg interest (0–100)
  Competition (35%)  — Inverse of Etsy listing count
  Monetisation (25%) — Average sale price normalised to 0–100

Themes scoring >= 60 proceed to Phase 2.
"""

PASS_THRESHOLD = 60

# Competition score mapping: listing_count → score
_COMP_FLOOR   =     500   # fewer than this → score 100
_COMP_CEILING = 100_000   # more than this  → score 0

# Monetisation score mapping: avg price → score
_PRICE_TARGET = 10.0      # $10 average = score 100


def score_theme(theme_data: dict) -> dict:
    """
    Score a single theme.

    Args:
        theme_data: dict with keys:
            theme           (str)
            avg_interest    (float)  — from google_trends()
            peak_interest   (float)  — from google_trends() — highest point in period
            listing_count   (int)    — from scan_etsy_listings()
            avg_price_usd   (float)  — from scan_etsy_prices() or scan_etsy_listings()

    Returns:
        {
            theme, slug,
            demand, competition, monetisation,  # component scores 0–100
            score,                               # composite 0–100
            proceed,                             # True if score >= 60
            listing_count, avg_price_usd, avg_interest,
        }
    """
    avg_interest  = float(theme_data.get("avg_interest", 0))
    peak_interest = float(theme_data.get("peak_interest", avg_interest))
    # Blend avg and peak: peak shows ceiling demand, avg shows consistency.
    # Weight peak more heavily — a high-peak, low-avg theme still has real demand.
    interest      = avg_interest * 0.35 + peak_interest * 0.65
    listing_count = int(theme_data.get("listing_count", 0))
    avg_price     = float(theme_data.get("avg_price_usd", 0))
    theme_name    = theme_data.get("theme", "")

    demand_score       = _score_demand(interest)
    competition_score  = _score_competition(listing_count)
    monetisation_score = _score_monetisation(avg_price)

    composite = (
        demand_score       * 0.40 +
        competition_score  * 0.35 +
        monetisation_score * 0.25
    )

    return {
        "theme":          theme_name,
        "slug":           _slugify(theme_name),
        "demand":         round(demand_score, 1),
        "competition":    round(competition_score, 1),
        "monetisation":   round(monetisation_score, 1),
        "score":          round(composite, 1),
        "proceed":        composite >= PASS_THRESHOLD,
        "listing_count":  listing_count,
        "avg_price_usd":  avg_price,
        "avg_interest":   interest,
    }


def rank_themes(scored_themes: list[dict]) -> list[dict]:
    """
    Sort a list of already-scored theme dicts by score descending.
    Returns all themes (caller decides whether to filter by proceed flag).
    """
    return sorted(scored_themes, key=lambda t: t["score"], reverse=True)


# ─── Component scorers ────────────────────────────────────────────────────────

def _score_demand(avg_interest: float) -> float:
    """Google Trends avg interest maps directly to 0–100."""
    return max(0.0, min(100.0, avg_interest))


def _score_competition(listing_count: int) -> float:
    """Fewer listings = less competition = higher score."""
    if listing_count <= _COMP_FLOOR:
        return 100.0
    if listing_count >= _COMP_CEILING:
        return 0.0
    return 100.0 * (1 - (listing_count - _COMP_FLOOR) / (_COMP_CEILING - _COMP_FLOOR))


def _score_monetisation(avg_price_usd: float) -> float:
    """Higher average price = higher monetisation score, capped at _PRICE_TARGET."""
    if avg_price_usd <= 0:
        return 20.0   # assume some baseline if no data
    return max(0.0, min(100.0, (avg_price_usd / _PRICE_TARGET) * 100))


def _slugify(text: str) -> str:
    import re
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
