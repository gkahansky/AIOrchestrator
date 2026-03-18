"""
Skill: log_cost
Record API/tool spend to the audit log in Google Drive.

Status: Sprint 5 — not yet implemented (basic stub for Tool Router use in Sprint 6).
"""


def log_cost(
    tool_id: str,
    capability: str,
    cost_usd: float,
    metadata: dict = None,
) -> dict:
    """
    Record a cost event.

    Returns:
        { logged: bool, tool_id, cost_usd }
    """
    # Sprint 1–5: no-op, returns without writing
    return {"logged": False, "tool_id": tool_id, "cost_usd": cost_usd}


def get_monthly_spend(tool_id: str) -> float:
    """
    Return total spend for a tool in the current calendar month.
    Used by the Tool Router budget cap check.

    Status: Sprint 6 — returns 0.0 until implemented.
    """
    return 0.0
