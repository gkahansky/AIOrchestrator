"""Platform dashboard router — GET /api/platform/dashboard."""

from fastapi import APIRouter, Depends

from aiplatform.database.models import Job
from aiplatform.database.session import get_db, ping as db_ping
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import DashboardResponse, VentureStats
from aiplatform.webapp.routers.health import _redis_ping

router = APIRouter()

_IN_PROGRESS_STATUSES = {
    "scraping", "scraped", "auditing", "audited", "generating_report",
    "transcribing", "transcribed", "generating", "generated",
    "packaging", "packaged", "delivering",
    "researching", "researched", "imaging", "imaged", "listing",
}
_REVIEW_STATUSES = {"review_pending"}
_DONE_STATUSES   = {"delivered", "published"}
_FAILED_STATUSES = {"failed", "cancelled"}

_VENTURES = ["etsy", "marketing_audit", "content_studio"]


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> DashboardResponse:
    from sqlalchemy import func
    from aiplatform.database.models import CostEvent, RevenueEvent
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    stats = []
    for venture in _VENTURES:
        rows = db.query(Job.status, func.count()).filter(
            Job.venture == venture
        ).group_by(Job.status).all()

        counts: dict[str, int] = {}
        for row_status, cnt in rows:
            counts[row_status] = cnt

        total     = sum(counts.values())
        pending   = counts.get("pending", 0)
        in_prog   = sum(v for k, v in counts.items() if k in _IN_PROGRESS_STATUSES)
        completed = sum(v for k, v in counts.items() if k in _DONE_STATUSES)
        failed    = sum(v for k, v in counts.items() if k in _FAILED_STATUSES)
        review    = sum(v for k, v in counts.items() if k in _REVIEW_STATUSES)

        stats.append(VentureStats(
            venture=venture,
            total_jobs=total,
            pending=pending,
            in_progress=in_prog,
            completed=completed,
            failed=failed,
            pending_review=review,
        ))

    cost_month = db.query(func.coalesce(func.sum(CostEvent.cost_usd), 0)).filter(
        func.extract("year",  CostEvent.created_at) == now.year,
        func.extract("month", CostEvent.created_at) == now.month,
    ).scalar() or 0.0

    rev_month = db.query(func.coalesce(func.sum(RevenueEvent.net_usd), 0)).filter(
        func.extract("year",  RevenueEvent.created_at) == now.year,
        func.extract("month", RevenueEvent.created_at) == now.month,
    ).scalar() or 0.0

    return DashboardResponse(
        ventures=stats,
        total_cost_usd_month=float(cost_month),
        total_revenue_usd_month=float(rev_month),
        db_ok=db_ping(),
        redis_ok=_redis_ping(),
    )
