"""Health check endpoint — no auth required."""

import os

from fastapi import APIRouter

from aiplatform.database.session import ping as db_ping
from aiplatform.webapp.schemas import HealthResponse

router = APIRouter()


def _redis_ping() -> bool:
    try:
        import redis as redis_lib
        r = redis_lib.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
        return r.ping()
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        db=db_ping(),
        redis=_redis_ping(),
    )
