"""
FastAPI application entry point.

Startup sequence:
  1. Materialise GOOGLE_SERVICE_ACCOUNT_JSON env var → google_service_account.json
  2. Verify DB connectivity (warn only — don't crash on startup)
  3. Mount all routers
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
from pathlib import Path

# Allow imports from src/
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aiplatform.database.session import ping as db_ping
from aiplatform.webapp.routers import health, jobs, dashboard, finance
from aiplatform.webapp.routers import etsy as etsy_router
from aiplatform.webapp.routers import marketing_audit as audit_router
from aiplatform.webapp.routers import content_studio as podcast_router

logger = logging.getLogger(__name__)

# ── Google service account — materialise from env var at startup ───────────────

def _materialise_service_account() -> None:
    b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not b64:
        return
    dest = Path(os.environ.get("GOOGLE_CREDENTIALS_PATH", "./google_service_account.json"))
    try:
        decoded = base64.b64decode(b64)
        json.loads(decoded)  # validate it's valid JSON
        dest.write_bytes(decoded)
        logger.info("Google service account written to %s", dest)
    except Exception as exc:
        logger.warning("Failed to materialise GOOGLE_SERVICE_ACCOUNT_JSON: %s", exc)


# ── App factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    _materialise_service_account()

    app = FastAPI(
        title="AI Platform API",
        description="Multi-venture AI business platform — MiroPrintStudio + EchoForge",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Platform routers
    app.include_router(health.router, tags=["platform"])
    app.include_router(jobs.router,      prefix="/api/jobs",      tags=["jobs"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
    app.include_router(finance.router,   prefix="/api/finance",   tags=["finance"])

    # Venture routers
    app.include_router(etsy_router.router,    prefix="/api/etsy",    tags=["etsy"])
    app.include_router(audit_router.router,   prefix="/api/audit",   tags=["marketing-audit"])
    app.include_router(podcast_router.router, prefix="/api/podcast", tags=["content-studio"])

    @app.on_event("startup")
    async def _startup() -> None:
        if db_ping():
            logger.info("Database: connected")
        else:
            logger.warning("Database: NOT connected — check DATABASE_URL")

    return app


app = create_app()
