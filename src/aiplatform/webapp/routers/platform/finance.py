"""Platform finance router — GET /api/platform/finance."""

from fastapi import APIRouter, Depends, Query

from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.webapp.schemas import CostSummary, FinanceResponse, RevenueSummary

router = APIRouter()


@router.get("", response_model=FinanceResponse)
def get_finance(
    year: int | None = Query(None),
    month: int | None = Query(None),
    _: str = Depends(require_auth),
    db=Depends(get_db),
) -> FinanceResponse:
    from datetime import datetime, timezone
    from sqlalchemy import func
    from aiplatform.database.models import CostEvent, RevenueEvent

    now = datetime.now(timezone.utc)
    y = year  or now.year
    m = month or now.month
    period = f"{y:04d}-{m:02d}"

    def _month_filter(col):
        return [
            func.extract("year",  col) == y,
            func.extract("month", col) == m,
        ]

    cost_rows = db.query(
        CostEvent.tool_id,
        CostEvent.capability,
        func.sum(CostEvent.cost_usd).label("total_cost"),
        func.count().label("call_count"),
    ).filter(*_month_filter(CostEvent.created_at)).group_by(
        CostEvent.tool_id, CostEvent.capability
    ).all()

    costs = [
        CostSummary(
            tool_id=r.tool_id,
            capability=r.capability,
            total_cost_usd=float(r.total_cost),
            call_count=r.call_count,
        )
        for r in cost_rows
    ]

    rev_rows = db.query(
        RevenueEvent.venture,
        RevenueEvent.source,
        func.sum(RevenueEvent.amount_usd).label("total_amount"),
        func.sum(RevenueEvent.fee_usd).label("total_fee"),
        func.sum(RevenueEvent.net_usd).label("total_net"),
        func.count().label("order_count"),
    ).filter(*_month_filter(RevenueEvent.created_at)).group_by(
        RevenueEvent.venture, RevenueEvent.source
    ).all()

    revenues = [
        RevenueSummary(
            venture=r.venture,
            source=r.source,
            total_amount_usd=float(r.total_amount),
            total_fee_usd=float(r.total_fee),
            total_net_usd=float(r.total_net),
            order_count=r.order_count,
        )
        for r in rev_rows
    ]

    total_cost = sum(c.total_cost_usd for c in costs)
    total_net  = sum(r.total_net_usd  for r in revenues)

    return FinanceResponse(
        costs=costs,
        revenues=revenues,
        net_usd=total_net - total_cost,
        period=period,
    )
