"""
Skill: log_cost
Record API/tool spend to the cost_events database table.

Caller passes venture + job_id when available; both are optional so that
platform-level costs (SerpAPI trend research, ClickUp sync) can be logged
without a job context.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from aiplatform.database.models import CostEvent
from aiplatform.database.session import get_session


def log_cost(
    tool_id: str,
    capability: str,
    cost_usd: float,
    metadata: dict = None,
    job_id: str | None = None,
    venture: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
) -> dict:
    """
    Record a cost event in the database.

    Args:
        tool_id:     e.g. "dalle3", "gemini-imagen", "claude-sonnet"
        capability:  e.g. "image-generation", "text-generation"
        cost_usd:    actual cost for this call
        metadata:    ignored — kept for backwards compatibility with call sites
        job_id:      UUID string of the parent job (nullable)
        venture:     e.g. "etsy", "marketing_audit", "content_studio" (nullable)
        tokens_in:   input tokens for LLM calls (nullable)
        tokens_out:  output tokens for LLM calls (nullable)

    Returns:
        { logged: bool, tool_id, cost_usd, event_id (if logged) }
    """
    try:
        parsed_job_id = uuid.UUID(job_id) if job_id else None
    except (ValueError, AttributeError):
        parsed_job_id = None

    try:
        with get_session() as db:
            event = CostEvent(
                job_id=parsed_job_id,
                venture=venture,
                capability=capability,
                tool_id=tool_id,
                cost_usd=cost_usd,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
            )
            db.add(event)
            db.flush()
            event_id = event.id
        return {"logged": True, "tool_id": tool_id, "cost_usd": cost_usd, "event_id": event_id}
    except SQLAlchemyError as exc:
        # Never block the caller — log and return logged=False
        print(f"[log_cost] DB write failed: {exc}")
        return {"logged": False, "tool_id": tool_id, "cost_usd": cost_usd}


def get_monthly_spend(tool_id: str) -> float:
    """
    Return total spend for a tool in the current calendar month.
    Used by the Tool Router budget cap check.
    """
    from sqlalchemy import func, extract
    from aiplatform.database.session import get_session
    from aiplatform.database.models import CostEvent

    now = datetime.now(timezone.utc)
    try:
        with get_session() as db:
            result = db.query(func.sum(CostEvent.cost_usd)).filter(
                CostEvent.tool_id == tool_id,
                extract("year", CostEvent.created_at) == now.year,
                extract("month", CostEvent.created_at) == now.month,
            ).scalar()
        return float(result or 0.0)
    except SQLAlchemyError:
        return 0.0
