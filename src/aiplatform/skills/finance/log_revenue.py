"""
Skill: log_revenue
Record a sale or delivery to the revenue_events database table.
"""

import uuid

from sqlalchemy.exc import SQLAlchemyError

from aiplatform.database.models import RevenueEvent
from aiplatform.database.session import get_session


def log_revenue(
    venture: str,
    source: str,
    amount_usd: float,
    fee_usd: float = 0.0,
    job_id: str | None = None,
    description: str | None = None,
) -> dict:
    """
    Record a revenue event in the database.

    Args:
        venture:     e.g. "marketing_audit", "content_studio", "etsy"
        source:      e.g. "fiverr", "etsy", "direct"
        amount_usd:  gross revenue for this sale
        fee_usd:     platform fee (Etsy commission, Fiverr cut, etc.)
        job_id:      UUID string of the parent job (nullable)
        description: optional free-text note

    Returns:
        { logged: bool, venture, amount_usd, net_usd, event_id (if logged) }
    """
    net_usd = round(amount_usd - fee_usd, 2)

    try:
        parsed_job_id = uuid.UUID(job_id) if job_id else None
    except (ValueError, AttributeError):
        parsed_job_id = None

    try:
        with get_session() as db:
            event = RevenueEvent(
                job_id=parsed_job_id,
                venture=venture,
                source=source,
                amount_usd=amount_usd,
                fee_usd=fee_usd,
                net_usd=net_usd,
                description=description,
            )
            db.add(event)
            db.flush()
            event_id = event.id

            # CRM ingestion (H-11): propagate revenue to the contact's lifetime
            # value and advance customer→repeat. Looked up via the parent job's
            # client_email. Best-effort — never fails the revenue write.
            if parsed_job_id is not None:
                try:
                    from aiplatform.database.models import Job
                    from aiplatform.database.crm_ops import add_revenue_to_contact
                    job = db.get(Job, parsed_job_id)
                    email = (job.input_data or {}).get("client_email") if job else None
                    if email:
                        add_revenue_to_contact(email, int(round(net_usd * 100)), db=db)
                except Exception as exc:
                    print(f"[log_revenue] CRM LTV propagation skipped: {exc}")
        return {
            "logged": True,
            "venture": venture,
            "amount_usd": amount_usd,
            "net_usd": net_usd,
            "event_id": event_id,
        }
    except SQLAlchemyError as exc:
        print(f"[log_revenue] DB write failed: {exc}")
        return {"logged": False, "venture": venture, "amount_usd": amount_usd, "net_usd": net_usd}
