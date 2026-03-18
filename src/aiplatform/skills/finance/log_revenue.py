"""
Skill: log_revenue
Record sales revenue from Etsy (or any other channel).

Status: Sprint 5 — not yet implemented.
"""


def log_revenue(
    listing_id: str,
    amount_usd: float,
    channel: str = "etsy",
    metadata: dict = None,
) -> dict:
    """
    Record a revenue event.

    Returns:
        { logged: bool, listing_id, amount_usd }
    """
    raise NotImplementedError("log_revenue is a Sprint 5 feature.")
