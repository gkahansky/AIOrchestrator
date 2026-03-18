"""
Skill: calculate_roas
Calculate Return on Ad Spend for a listing or campaign.

Status: Sprint 5 — not yet implemented.

ROAS tiers (from CLAUDE.md):
  < 2×   → pause ads
  2–4×   → maintain budget
  > 4×   → increase to $3–$5/day
"""


def calculate_roas(listing_id: str, period_days: int = 30) -> dict:
    """
    Calculate ROAS for a listing over the given period.

    Returns:
        {
            listing_id, period_days,
            revenue_usd, ad_spend_usd, roas,
            recommendation  # 'pause' | 'maintain' | 'increase'
        }
    """
    raise NotImplementedError("calculate_roas is a Sprint 5 feature.")
