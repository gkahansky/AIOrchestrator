"""
FastAPI application entry point.

Startup sequence:
  1. Materialise GOOGLE_SERVICE_ACCOUNT_JSON env var → google_service_account.json
  2. Verify DB connectivity (warn only — don't crash on startup)
  3. Mount all routers

URL layout (per migration plan):
  GET  /api/health
  GET  /api/jobs, GET /api/jobs/{id}
  POST /api/jobs/{id}/approve|reject|retry|cancel
  GET  /api/platform/dashboard
  GET  /api/platform/finance
  GET/PUT  /api/platform/settings/keys/{service}
  POST     /api/platform/settings/keys/{service}/test
  PUT      /api/platform/settings/tools/{capability}/{tool_id}
  POST /api/ventures/etsy/phase/{n}
  GET  /api/ventures/etsy/listings
  POST /api/ventures/marketing-audit/orders
  POST /api/ventures/content-studio/orders
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
from aiplatform.webapp.routers import health
from aiplatform.webapp.routers.platform import auth as platform_auth
from aiplatform.webapp.routers.platform import jobs as platform_jobs
from aiplatform.webapp.routers.platform import dashboard as platform_dashboard
from aiplatform.webapp.routers.platform import finance as platform_finance
from aiplatform.webapp.routers.platform import settings as platform_settings
from aiplatform.webapp.routers.platform import gigs as platform_gigs
from aiplatform.webapp.routers.platform import strategy as platform_strategy
from aiplatform.webapp.routers.webhooks import github as webhooks_github
from aiplatform.webapp.routers.ventures import etsy as ventures_etsy
from aiplatform.webapp.routers.ventures import marketing_audit as ventures_audit
from aiplatform.webapp.routers.ventures import content_studio as ventures_podcast
from aiplatform.webapp.routers import accessibility as audit_accessibility
from aiplatform.webapp.routers.public import sample as public_sample

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Google service account — materialise from env var at startup ───────────────

def _materialise_service_account() -> None:
    # OAuth user token — preferred for personal Drive writes
    token_b64 = os.environ.get("GOOGLE_DRIVE_TOKEN_JSON", "")
    if token_b64:
        dest = Path(os.environ.get("GOOGLE_TOKEN_PATH", "./google_token.json"))
        try:
            dest.write_bytes(base64.b64decode(token_b64))
            logger.info("Google OAuth token written to %s", dest)
        except Exception as exc:
            logger.warning("Failed to write Google OAuth token: %s", exc)

    # Service account — fallback
    b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not b64:
        return
    dest = Path(os.environ.get("GOOGLE_CREDENTIALS_PATH", "./google_service_account.json"))
    try:
        decoded = base64.b64decode(b64)
        json.loads(decoded)  # validate it's valid JSON before writing
        dest.write_bytes(decoded)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(dest.resolve())
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

    origins = os.environ.get("CORS_ORIGINS", "*").split(",")
    # allow_credentials cannot be used with wildcard origin (CORS spec)
    allow_creds = origins != ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_creds,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Health — no auth, no prefix (returns at /api/health)
    app.include_router(health.router, prefix="/api", tags=["platform"])

    # Auth — no auth required (issues tokens)
    app.include_router(platform_auth.router, prefix="/api/auth", tags=["auth"])

    # Platform — jobs, dashboard, finance, settings
    app.include_router(platform_jobs.router,     prefix="/api/jobs",                        tags=["jobs"])
    app.include_router(platform_dashboard.router, prefix="/api/platform/dashboard",          tags=["platform"])
    app.include_router(platform_finance.router,   prefix="/api/platform/finance",            tags=["platform"])
    app.include_router(platform_settings.router,  prefix="/api/platform/settings",           tags=["settings"])
    app.include_router(platform_gigs.router,      prefix="/api/platform/gigs",               tags=["platform"])
    app.include_router(platform_strategy.router,  prefix="/api/platform/strategy",           tags=["platform"])

    # Ventures
    app.include_router(ventures_etsy.router,    prefix="/api/ventures/etsy",              tags=["etsy"])
    app.include_router(ventures_audit.router,   prefix="/api/ventures/marketing-audit",   tags=["marketing-audit"])
    app.include_router(ventures_podcast.router, prefix="/api/ventures/content-studio",    tags=["content-studio"])    app.include_router(audit_accessibility.router,      prefix="/api/audit/accessibility",        tags=["accessibility"])
    # Public (no auth) — free sample requests from echoforge.biz
    app.include_router(public_sample.router,    prefix="/api/sample",                     tags=["public"])    
    # Webhooks (Github, Stripe etc)
    app.include_router(webhooks_github.router,  prefix="/api/webhooks",           tags=["webhooks"])
    @app.on_event("startup")
    async def _startup() -> None:
        if db_ping():
            logger.info("Database: connected")
        else:
            logger.warning("Database: NOT connected — check DATABASE_URL")

    return app


app = create_app()
