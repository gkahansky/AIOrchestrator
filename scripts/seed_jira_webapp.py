"""
One-time script: seed Jira with Cloud Migration + Management Web App features,
stories, and tasks. Adds all issues to SCRUM Sprint 1.
"""
import urllib.request
import urllib.error
import json
import base64
import os
import sys

from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".ENV")

API_KEY  = os.environ["JIRA_API_KEY"]
EMAIL    = os.environ["JIRA_EMAIL"]
DOMAIN   = os.environ["JIRA_DOMAIN"]
PROJECT  = "AII"
USER_ID  = "5b2a55078b08c009c48b38ea"  # gkahansky@gmail.com
SPRINT_ID = 1

creds   = base64.b64encode(f"{EMAIL}:{API_KEY}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {creds}",
    "Content-Type":  "application/json",
    "Accept":        "application/json",
}

TYPES = {"Feature": "10005", "Story": "10004", "Task": "10003"}


def jira(method, path, body=None):
    url  = DOMAIN + path
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  ERROR {e.code} on {method} {path}: {err[:300]}")
        return None


def create_issue(summary, itype, description="", parent_key=None, assignee=None):
    body = {
        "fields": {
            "project":   {"key": PROJECT},
            "summary":   summary,
            "issuetype": {"id": TYPES[itype]},
        }
    }
    if description:
        body["fields"]["description"] = {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
        }
    if parent_key:
        body["fields"]["parent"] = {"key": parent_key}
    if assignee:
        body["fields"]["assignee"] = {"id": assignee}
    result = jira("POST", "/rest/api/3/issue", body)
    if result:
        label = "[HUMAN] " if assignee else ""
        print(f"    {result['key']}  {label}{summary[:70]}")
    return result


def add_to_sprint(key):
    jira("POST", f"/rest/agile/1.0/sprint/{SPRINT_ID}/issue", {"issues": [key]})


def feature(summary, description):
    r = create_issue(summary, "Feature", description)
    if r:
        add_to_sprint(r["key"])
    return r["key"] if r else None


def story(summary, description, parent):
    r = create_issue(summary, "Story", description, parent_key=parent)
    if r:
        add_to_sprint(r["key"])
    return r["key"] if r else None


def task(summary, description, parent, human=False):
    r = create_issue(summary, "Task", description, parent_key=parent,
                     assignee=USER_ID if human else None)
    if r:
        add_to_sprint(r["key"])
    return r["key"] if r else None


# ─── FEATURE 1: Cloud Infrastructure Migration ─────────────────────────────
print("\n=== Feature 1: Cloud Infrastructure Migration ===")
# AII-93 already created in previous run - reuse it
F1 = "AII-93"
add_to_sprint(F1)
print(f"  Reusing existing Feature 1: {F1}")
if False: F1 = feature(
    "Cloud Infrastructure Migration",
    "Migrate AI-Infra platform from local CLI scripts to Railway cloud. "
    "Add PostgreSQL, Celery job queue, FastAPI backend. "
    "Prod + staging environments with full cost isolation for testing.",
)
if not F1:
    print("Failed to create/find Feature 1. Aborting.")
    sys.exit(1)

# Story 1.1
print("  Story 1.1 - Phase 0: Database Foundation")
S = story(
    "Phase 0 - Database Foundation",
    "SQLAlchemy models, Alembic migrations, implement log_cost(), "
    "OUTPUT_DIR env var, ai-marketing-claude submodule. "
    "All local - no behaviour change to existing CLI workflows.",
    F1,
)
task("Set up local PostgreSQL for development", "Run: docker run -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres:16. Verify connection. Required for Phase 0/1 development before cloud deployment.", S, human=True)
task("Create SQLAlchemy models + Alembic migrations",
     "Create src/aiplatform/database/models.py (Job, PhaseEvent, CostEvent, RevenueEvent) and session.py. "
     "Initialise Alembic in alembic/. Run first migration against local DB.", S)
task("Implement log_cost() DB insert",
     "Replace stub in src/aiplatform/skills/finance/log_cost.py. "
     "Insert row into cost_events table. ~15 lines. Called by every pipeline phase.", S)
task("Add OUTPUT_DIR env var to all venture configs",
     "Replace hardcoded ./output/ paths with os.getenv('OUTPUT_DIR', './output') "
     "in etsy, marketing_audit, content_studio config.py. No behaviour change locally.", S)
task("Add ai-marketing-claude as git submodule",
     "Run: git submodule add <repo-url> ai-marketing-claude. "
     "Update sibling-repo path resolution in marketing_audit/pipeline.py to use submodule path. "
     "Required for Railway where sibling directories do not exist.", S)

# Story 1.2
print("  Story 1.2 - Phase 1: DB-Backed Pipeline State")
S = story(
    "Phase 1 - Database-Backed Pipeline State",
    "Wire all three pipeline _save_order() calls to write to PostgreSQL "
    "alongside existing JSON files. Create JSON-to-DB migration script.",
    F1,
)
task("Wire pipeline state writes to PostgreSQL",
     "In etsy, marketing_audit, content_studio pipeline.py: "
     "add DB upsert to _save_order() alongside existing JSON write. "
     "Load jobs from DB when resuming (--order-id flag). "
     "JSON files remain as local debug fallback.", S)
task("Create scripts/migrate_json_to_db.py",
     "One-time script: read all output/*/order.json files, "
     "insert each as a row in jobs table. "
     "Idempotent - skip rows where order_id already exists.", S)

# Story 1.3
print("  Story 1.3 - Phase 2: FastAPI + Celery Backend")
S = story(
    "Phase 2 - FastAPI + Celery Backend",
    "Build webapp/main.py, all API routers, Celery worker tasks. "
    "Implement human review approval endpoint. Write Dockerfile and railway.toml.",
    F1,
)
task("Build webapp/main.py, auth.py, schemas.py",
     "Create src/aiplatform/webapp/main.py: FastAPI app factory, "
     "startup events (Drive service account materialisation from GOOGLE_SERVICE_ACCOUNT_JSON env var), "
     "CORS, bearer token auth middleware. "
     "auth.py: HTTPBearer dependency checking DASHBOARD_API_KEY. "
     "schemas.py: Pydantic request/response models for all endpoints.", S)
task("Build platform API routers - jobs, dashboard, finance, settings",
     "routers/platform/jobs.py: GET /api/jobs, GET /api/jobs/{id}, "
     "POST /api/jobs/{id}/approve|reject|retry|cancel. "
     "dashboard.py: aggregated stats. finance.py: cost/revenue/P&L. "
     "settings.py: API keys, tool router toggles, notifications, Drive folder management.", S)
task("Build venture API routers - etsy, marketing-audit, content-studio",
     "routers/ventures/etsy.py: POST /api/ventures/etsy/phase/{n}, GET /api/ventures/etsy/listings. "
     "marketing_audit.py: POST /api/ventures/marketing-audit/orders, GET list + detail. "
     "content_studio.py: POST multipart order with audio upload, GET list + detail. "
     "Each router imports only from its own venture pipeline and config.", S)
task("Build worker.py - Celery app + one task per venture pipeline",
     "src/aiplatform/worker.py: Celery app factory (Redis broker). "
     "Tasks: run_etsy_pipeline, run_audit_pipeline, run_podcast_pipeline. "
     "Each task: load job from DB, run pipeline, update status. "
     "Review gate pause: task sets status=review_pending and re-enqueues itself with countdown=1800. "
     "Approval endpoint resumes immediately by re-enqueuing with countdown=0.", S)
task("Write Dockerfile and railway.toml",
     "Dockerfile: python:3.11-slim base, copy src/ + requirements.txt, "
     "install deps, expose port 8000. "
     "railway.toml: two services - web (uvicorn src.aiplatform.webapp.main:app) "
     "and worker (celery -A src.aiplatform.worker worker). "
     "Health check on GET /api/health.", S)

# Story 1.4
print("  Story 1.4 - Phase 3: Cloud Infrastructure Setup (human tasks)")
S = story(
    "Phase 3 - Cloud Infrastructure Setup",
    "All account creation, service provisioning, and credential migration tasks. "
    "Must be completed before Railway staging deployment.",
    F1,
)
task("[HUMAN] Create Railway account and project",
     "Sign up at railway.app. Connect GitHub repo (AIOrchestrator). "
     "Create project named AIOrchestrator. "
     "Create two environments: production (main branch) and staging (develop branch). "
     "Add PostgreSQL plugin to each environment. "
     "Set start commands: web=uvicorn src.aiplatform.webapp.main:app --host 0.0.0.0 --port $PORT, "
     "worker=celery -A src.aiplatform.worker worker --loglevel=info", S, human=True)
task("[HUMAN] Create Vercel account for frontend",
     "Sign up at vercel.com. Connect GitHub repo. "
     "Vercel will auto-deploy the frontend/ directory on push to main.", S, human=True)
task("[HUMAN] Create Redis Cloud account",
     "Sign up at redis.io (free tier, 30 MB). "
     "Create one database. Copy connection URL to Railway env vars as REDIS_URL for both environments. "
     "Use different database indices for staging vs prod (add ?db=0 and ?db=1 suffix).", S, human=True)
task("[HUMAN] Create Google Cloud service account for cloud deployment",
     "In Google Cloud Console: IAM & Admin > Service Accounts > Create. "
     "Name: aiinfra-cloud-deploy (separate from local OAuth account). "
     "Grant: Google Drive API access (Editor on Drive folders). "
     "Download JSON key file. "
     "Base64-encode: base64 -i service-account.json (on Mac/Linux) or certutil -encode on Windows. "
     "Store encoded value as GOOGLE_SERVICE_ACCOUNT_JSON in Railway env vars.", S, human=True)
task("[HUMAN] Share Drive folders with cloud service account",
     "Open each Drive folder: EtsyShop, PodcastNotes, MarketingAudits (and all subfolders). "
     "Share with service account email (format: name@project.iam.gserviceaccount.com) as Editor. "
     "Create /AIOrchestrator-Staging/ folder hierarchy with same subfolders. "
     "Share staging folders with same service account. "
     "Copy staging folder IDs to Railway staging env vars (DRIVE_01_RESEARCH_ID etc).", S, human=True)
task("[HUMAN] Migrate all .ENV secrets to Railway environment variables",
     "Add every variable from .ENV file to Railway staging environment "
     "with these overrides for cost isolation: "
     "IMAGE_GEN_MOCK=true, TRANSCRIPTION_MOCK=true, NOTIFICATIONS_ENABLED=false, "
     "CLAUDE_MAX_TOKENS=512, DRIVE_* = staging folder IDs, ETSY_* = sandbox credentials. "
     "Add DASHBOARD_API_KEY = 32-char random string (used for management app auth). "
     "Repeat for production with all real values and mocks disabled.", S, human=True)
task("[HUMAN] Request Etsy sandbox credentials",
     "Log into Etsy developer console (developer.etsy.com). "
     "Request sandbox/test environment credentials. "
     "Add sandbox ETSY_API_KEY, ETSY_API_SECRET, ETSY_SHOP_ID to Railway staging env vars.", S, human=True)
task("[HUMAN] Set up DNS for api.echoforge.biz",
     "In your DNS provider: add CNAME record: api.echoforge.biz -> Railway production web service domain. "
     "Railway auto-provisions SSL cert. Verify HTTPS is working after ~10 mins.", S, human=True)

# Story 1.5
print("  Story 1.5 - Phase 4: Staging Validation + Production Cutover")
S = story(
    "Phase 4 - Staging Validation + Production Cutover",
    "End-to-end testing on Railway staging. Run DB migration. Final production cutover.",
    F1,
)
task("Deploy to Railway staging and run end-to-end tests",
     "Push develop branch. Verify Railway deploys both web + worker services. "
     "Test each venture pipeline via HTTP (mock mode - no real API costs). "
     "Verify: DB writes, Drive uploads to /AIOrchestrator-Staging/, approval endpoints, "
     "Celery task pause/resume for review gates.", S)
task("Run migrate_json_to_db.py against production DB",
     "After production Railway environment is configured: "
     "run python scripts/migrate_json_to_db.py against the production DATABASE_URL. "
     "Verify row counts match local output/ directory order count.", S)
task("[HUMAN] Final production cutover",
     "Merge develop to main. Verify Railway production deployment. "
     "Confirm api.echoforge.biz is reachable via HTTPS. "
     "Test one real pipeline run end-to-end (e.g. marketing audit on echoforge.biz). "
     "Local CLI still works as fallback - no need to remove.", S, human=True)

print(f"\n  Feature 1 done: {F1}")


# ─── FEATURE 2: Management Web App ─────────────────────────────────────────
print("\n=== Feature 2: Management Web App ===")
F2 = feature(
    "Management Web App",
    "React + FastAPI web application to manage all AI-Infra ventures. "
    "Replaces manual CLI scripts and JSON file editing. "
    "Dashboard, per-venture pipeline control, human review gates, finance, settings.",
)
if not F2:
    print("Failed to create Feature 2. Aborting.")
    sys.exit(1)

# Story 2.1
print("  Story 2.1 - Platform API Layer")
S = story(
    "Platform API - Jobs, Dashboard, Finance, Settings",
    "All platform-wide FastAPI endpoints: job lifecycle management, "
    "dashboard aggregation, finance/cost summary, settings management.",
    F2,
)
task("Jobs API - list, detail, approve, reject, retry, cancel",
     "GET /api/jobs (filter by venture/status/date), GET /api/jobs/{id}. "
     "POST /api/jobs/{id}/approve: sets status=approved, re-enqueues Celery task immediately. "
     "POST /api/jobs/{id}/reject: sets status=rejected with optional notes. "
     "POST /api/jobs/{id}/retry: from last checkpoint or from start. "
     "POST /api/jobs/{id}/cancel: kills Celery task, sets status=cancelled.", S)
task("Dashboard API - aggregated platform stats",
     "GET /api/platform/dashboard returns: "
     "active_jobs (count), review_queue (list with venture/summary/phase/wait_time), "
     "kpis (revenue_mtd, cost_mtd, net_mtd), "
     "recent_completions (last 10), failed_jobs (list), "
     "system_health (worker/db/redis/drive status, api_key_status per service).", S)
task("Finance API - revenue, cost, P&L, ROAS",
     "GET /api/platform/finance?range=month|3m|12m|custom. "
     "Returns: monthly_revenue (by venture), monthly_cost (by tool), "
     "pnl_per_venture (revenue/cost/net/margin), "
     "etsy_roas (per listing: ad_spend/revenue/roas/recommendation).", S)
task("Settings API - keys, tool router, notifications, Drive folders",
     "GET/PUT /api/platform/settings/keys/{service}: masked key display, update, test endpoint. "
     "PUT /api/platform/settings/tools/{capability}/{tool_id}: toggle active (writes to DB, "
     "tool_router.py reads from DB at runtime replacing skills.json). "
     "GET/PUT /api/platform/settings/notifications. "
     "GET /api/platform/settings/drive/{venture}: verify + rescan folders.", S)
task("Health check endpoint",
     "GET /api/health: check DB connection, Redis ping, "
     "Celery worker heartbeat, Google Drive API test call. "
     "Return {healthy: bool, services: {db/redis/worker/drive: ok|error}}.", S)

# Story 2.2
print("  Story 2.2 - Venture API Routers")
S = story(
    "Venture API Routers - Etsy, Marketing Audit, Content Studio",
    "FastAPI routers per venture. Trigger pipeline phases, manage orders, query outputs.",
    F2,
)
task("Etsy venture router - phase triggers + listings",
     "POST /api/ventures/etsy/phase/{1-7}: enqueue Celery task for that phase with slug param. "
     "GET /api/ventures/etsy/listings: all subjects by status with metadata + Drive links. "
     "POST /api/ventures/etsy/listings/{slug}/approve: inline edit payload "
     "(optional updated title/description/tags). "
     "POST /api/ventures/etsy/listings/{slug}/regenerate: send back to phase 3.", S)
task("Marketing Audit venture router - orders CRUD",
     "POST /api/ventures/marketing-audit/orders: create order, enqueue pipeline. "
     "Body: url, tier, brand_name, competitor_urls[], client_context, client_email, report_type. "
     "GET /api/ventures/marketing-audit/orders: list with status/tier/date filters. "
     "GET /api/ventures/marketing-audit/orders/{id}: full detail including "
     "scrape results, audit scores (6 dimensions), report PDF links.", S)
task("Content Studio venture router - orders + audio upload",
     "POST /api/ventures/content-studio/orders: multipart form with audio file + order metadata. "
     "Handles demo mode (no audio). Enqueues pipeline. "
     "GET list + GET detail: includes transcript, per-section content, add-on results, Drive links.", S)

# Story 2.3
print("  Story 2.3 - Frontend React App (deferred - awaiting design)")
S = story(
    "Frontend React App - Management Dashboard",
    "React + Vite SPA. BLOCKED on Google Stitch design delivery. "
    "Covers all 7 sections: Dashboard, Etsy, Marketing Audit, Podcast Notes, "
    "Finance, Settings, Job Detail.",
    F2,
)
task("[HUMAN] Provide Google Stitch UI design + MD specification",
     "Supply the Google Stitch design project export and the accompanying UI specification MD file. "
     "Required before frontend implementation begins. "
     "Functional requirements are documented in docs/cloud-migration-plan.md (Document 2).", S, human=True)
task("Set up React + Vite project scaffold",
     "BLOCKED on design delivery. "
     "Once design received: init frontend/ with Vite + React + TypeScript + shadcn/ui. "
     "Configure Vercel deployment (vercel.json). "
     "Set up API client (axios or fetch wrapper) pointing to VITE_API_URL env var.", S)
task("Dashboard page - KPIs, review queue, system health",
     "BLOCKED on design. "
     "Platform overview: active jobs count, review queue with approve/reject, "
     "revenue/cost/net KPI cards, failed jobs alert, system health panel. "
     "See Document 2 Section 1 in cloud-migration-plan.md.", S)
task("Etsy venture pages - pipeline control, listings, review queue",
     "BLOCKED on design. "
     "Tabs: Overview, Pipeline Control (per-phase trigger cards), "
     "Listings browser (thumbnail gallery), Review Queue (approve/reject/edit/regenerate), Settings. "
     "See Document 2 Section 2 in cloud-migration-plan.md.", S)
task("Marketing Audit pages - new order form, orders list, job detail",
     "BLOCKED on design. "
     "New order form with tier radio, competitor URL rows, client context. "
     "Orders list with filters. Job detail: scrape results, 6-dimension score bars, "
     "approve/deliver gate. "
     "See Document 2 Section 3 in cloud-migration-plan.md.", S)
task("Podcast Notes pages - new order form, orders list, job detail",
     "BLOCKED on design. "
     "Audio upload with progress, tier + add-on selection. "
     "Orders list. Job detail: transcript, section tabs, add-on results, approve gate. "
     "See Document 2 Section 4 in cloud-migration-plan.md.", S)
task("Finance pages - revenue, cost, P&L, ROAS charts",
     "BLOCKED on design. "
     "Monthly revenue chart, cost-by-tool table, P&L per venture, "
     "Etsy ROAS per listing with bulk recommendations. "
     "See Document 2 Section 5 in cloud-migration-plan.md.", S)
task("Settings pages - API keys, tool router, notifications, Drive",
     "BLOCKED on design. "
     "API key table with test/edit, tool router active toggles (no redeployment), "
     "notification config, Drive folder verify/rescan. "
     "See Document 2 Section 6 in cloud-migration-plan.md.", S)

print(f"\n  Feature 2 done: {F2}")
print(f"\nAll done. Feature 1: {F1} | Feature 2: {F2}")
print("All issues created and added to SCRUM Sprint 1.")
