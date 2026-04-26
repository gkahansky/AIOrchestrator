# AI-Infra Platform — Tool Stack

Complete inventory of every third-party tool, service, API, and library used across the AIOrchestrator platform (MiroPrintStudio + EchoForge ventures).

---

## AI & LLM

| Tool | Purpose | Use Cases |
|---|---|---|
| **Anthropic Claude API** (`anthropic>=0.40.0`) | Primary LLM for all agent intelligence | Marketing audit report generation, Etsy listing copy, podcast show notes, theme research, SEO metadata, content scoring, market research decomposer/package-merge/stitch/critic |
| **OpenAI API** (`openai>=1.30.0`) | Audio transcription + image generation + embeddings | Whisper for podcast audio → transcript; DALL-E 3 as primary image generator; `text-embedding-3-small` for RAG embeddings in market research |
| **Google Gemini / Generative AI** (`google-genai`, `google-generativeai`) | Image generation + multimodal + research | Gemini Imagen 3 for AI-generated wall art (pending billing approval); `gemini-2.0-flash-001` as research committee member in Market Research |
| **xAI Grok API** (OpenAI-compatible at `https://api.x.ai/v1`) | LLM research + critic | `grok-3-mini` participates in Market Research committee and as default critic/reflection model. Key aliases: `XAI_API_KEY`, `GROK_API_KEY`, `X_AI_API_KEY` |

---

## Google Platform

| Tool | Purpose | Use Cases |
|---|---|---|
| **Google Drive API** (`google-api-python-client`) | Primary asset storage layer | Upload generated images, PDFs, ZIPs, mockups; organise venture folder trees; share review files |
| **Google Docs API** (`google-api-python-client`) | Document creation | Create Google Docs from podcast show notes for client delivery |
| **Google OAuth 2.0** (`google-auth`, `google-auth-oauthlib`) | User-level Drive auth (5TB quota) | Preferred auth method at runtime; materialised from `GOOGLE_DRIVE_TOKEN_JSON` env var on Railway startup |
| **Google Service Account** (`google-auth`) | Fallback Drive auth | Used when OAuth token is not configured; limited to 15GB service account quota |
| **Google Identity Services** | Web app login | Google OAuth login for the management console (`planBadmin.com`) |
| **SerpAPI** | Google Search + Trends proxy | Etsy theme research (demand/competition scoring), competitor price monitoring, keyword trend analysis |

---

## Web Framework & API Layer

| Tool | Purpose | Use Cases |
|---|---|---|
| **FastAPI** (`fastapi>=0.111.0`) | REST API framework | All HTTP endpoints: venture triggers, job management, approve/reject gates, public sample endpoints |
| **Uvicorn** (`uvicorn>=0.29.0`) | ASGI server | Serves the FastAPI application in production (Railway web service) |
| **PyJWT** (`PyJWT>=2.8.0`) | Session tokens | Issues and verifies 24-hour JWT sessions after Google OAuth login |
| **python-multipart** (`python-multipart>=0.0.9`) | Form + file upload parsing | Handles multipart/form-data for audio file uploads on the podcast sample endpoint |
| **httpx** (`httpx>=0.27.0`) | Async HTTP client | Async API calls within FastAPI routes |
| **requests** (`requests>=2.31.0`) | Sync HTTP client | Skills layer: Etsy API, SerpAPI, Slack, Jira, Resend, Pinterest, website scraping |

---

## Frontend

| Tool | Purpose | Use Cases |
|---|---|---|
| **React** (v18) | UI framework | Management console SPA at `planBadmin.com` |
| **Vite** | Build tool + dev server | Frontend build, HMR during development, production bundle |
| **TypeScript** | Type-safe frontend | All frontend source code |
| **TailwindCSS** | Styling | Utility-first CSS across all UI components |
| **TanStack Query (React Query)** | Server state management | API data fetching, caching, background refetch, optimistic updates |
| **React Router** | Client-side routing | Navigation between Dashboard, Ventures, Finance, Settings pages |
| **PostCSS + Autoprefixer** | CSS transforms | Vendor prefix injection for cross-browser compatibility |
| **ESLint** | Code quality | JavaScript/TypeScript linting |

---

## Database & ORM

| Tool | Purpose | Use Cases |
|---|---|---|
| **PostgreSQL** (Railway plugin) | Primary database | Stores jobs, phase events, cost events, revenue events |
| **SQLAlchemy** (`sqlalchemy>=2.0.0`) | ORM | All database reads/writes: job state, upserts, phase tracking, cost logging |
| **Alembic** (`alembic>=1.13.0`) | Schema migrations | Version-controlled database schema changes; runs automatically on Railway deploy |
| **psycopg2-binary** (`psycopg2-binary>=2.9.0`) | PostgreSQL adapter | Low-level driver used by SQLAlchemy |

---

## Job Queue & Async

| Tool | Purpose | Use Cases |
|---|---|---|
| **Celery** (`celery>=5.3.0`) | Task queue | Runs all venture pipelines asynchronously (podcast, audit, Etsy phases); background processing |
| **Redis** (`redis>=5.0.0`) | Message broker + cache | Celery task broker; session state; pub/sub for real-time job status |

---

## Communications & Notifications

| Tool | Purpose | Use Cases |
|---|---|---|
| **Resend** (REST API via `requests`) | Transactional email | Order confirmations, PDF delivery emails, review notifications, sample report delivery |
| **Gmail SMTP** | Email inbox polling | Fiverr order intake — polls Gmail for Fiverr order confirmation emails |
| **Slack API** | Internal notifications | Phase completion alerts, review gate notifications, error alerts, pipeline status updates |

---

## Image Processing & Document Generation

| Tool | Purpose | Use Cases |
|---|---|---|
| **Pillow** (`Pillow>=10.3.0`) | Image manipulation | Resize generated images to required aspect ratios, create product mockups, composite overlays |
| **numpy** (`numpy>=1.26.0`) | Numerical operations | Image array operations during resizing and mockup generation |
| **Playwright** (`playwright`) | HTML→PDF rendering + browser automation | Security audit Phase 5 (authenticated crawl, IDOR, session testing); PDF generation for Security Audit and Market Research reports |
| **fpdf2** (`fpdf2>=2.7.0`) | PDF generation | Etsy review sheets, podcast sample PDFs, marketing audit PDF reports |
| **reportlab** (`reportlab>=4.0.0`) | PDF generation (alternative) | Reserved for advanced PDF layouts (Hebrew/RTL documents) |
| **arabic-reshaper** (`arabic-reshaper>=3.0.0`) | Arabic text shaping | Correct rendering of Arabic characters in PDFs |
| **python-bidi** (`python-bidi>=0.4.2`) | Bidirectional text | Right-to-left text layout for Hebrew and Arabic content in reports |
| **FFmpeg** (system binary via nixpacks) | Video/audio processing | Extract audio track from video files (.mp4/.mov/.mkv/.avi/.webm) before Whisper transcription — Service B (Content Repurposing Pack). Installed via `nixpacks.toml` nixPkgs on Railway. |
| **python-docx** (`python-docx>=1.1.0`) | Word document parsing | Extract text from DOCX/DOC files uploaded as RAG documents in Market Research |
| **openpyxl** (`openpyxl>=3.1.0`) | Excel spreadsheet parsing | Extract cell data from XLSX/XLS files uploaded as RAG documents in Market Research |
| **python-pptx** (`python-pptx>=0.6.23`) | PowerPoint parsing | Extract slide text from PPTX/PPT files uploaded as RAG documents in Market Research |

---

## Marketplace & E-commerce

| Tool | Purpose | Use Cases |
|---|---|---|
| **Etsy Open API v3** (REST via `requests`) | Etsy shop management | Create draft listings, upload listing images, attach digital download ZIPs, poll publish status |
| **Fiverr** (Gmail-based order intake) | Freelance order intake | Receives Fiverr order confirmation emails, parses order details, triggers venture pipelines |
| **Upwork API** *(planned)* | Alternative order intake | Secondary freelance channel — deferred, Fiverr-first strategy |

---

## Social Media & Promotion

| Tool | Purpose | Use Cases |
|---|---|---|
| **Pinterest API v5** *(stub — not yet implemented)* | Pin creation | Publish product images to Pinterest boards for Etsy traffic |
| **Buffer API** *(stub — not yet implemented)* | Social scheduling | Schedule posts to Instagram, Facebook, LinkedIn across ventures |

---

## Project Management

| Tool | Purpose | Use Cases |
|---|---|---|
| **Jira Cloud API v3** | Issue tracking | Create/update/transition tickets, sync pipeline phase status to Jira board (AII project). Skill: `comms/update_jira_board.py` |

---

## Infrastructure & Deployment

| Tool | Purpose | Use Cases |
|---|---|---|
| **Railway** | Cloud compute platform | Hosts FastAPI web service + Celery worker service; PostgreSQL plugin; staging and production environments |
| **Docker** | Container image | Reproducible Railway builds; includes system deps for psycopg2, Pillow, arabic text libs |
| **GitHub Actions** | CI/CD | Runs pytest on every PR; gates merges to main; PostgreSQL service container for integration tests |
| **Cloudflare** | DNS + CDN | DNS management for `echoforge.biz` and `planBadmin.com`; DDoS protection; SSL |

---

## Vector Database & Observability

| Tool | Purpose | Use Cases |
|---|---|---|
| **Qdrant Cloud** (`qdrant-client>=1.9.0`) | Vector database | **Live** — Market Research RAG: ingests user-uploaded documents, retrieves context per session (`market_research_rag` collection). Gracefully skipped if `QDRANT_URL` not set. |
| **LangSmith** *(planned)* | Agent observability | Trace Claude API calls, token usage, cost per pipeline phase; debugging |

---

## Utility Libraries

| Tool | Purpose | Use Cases |
|---|---|---|
| **python-dotenv** (`python-dotenv>=1.0.0`) | Environment config | Loads `.env` file for local development; no-op in production (Railway injects env vars) |
| **pytest** + **pytest-asyncio** | Testing | Unit tests for each skill in isolation; integration tests per venture pipeline |

---

## Authentication Flow (End-to-End)

```
Browser → Google Identity Services → Google OAuth callback
       → FastAPI auth.py validates Google token
       → Issues PyJWT session token (24h)
       → React stores JWT → sends as Bearer header on all API requests
       → FastAPI auth dependency validates JWT on every protected route
```

---

## Tool Selection Logic — Image Generation

The Tool Router (`src/aiplatform/registry/tool_router.py`) picks image tools at runtime based on `skills.json`:

| Priority | Tool | Status | Cost/call | Notes |
|---|---|---|---|---|
| 1 | DALL-E 3 (OpenAI) | Active (standard) | $0.04 | Current primary |
| 2 | Gemini Imagen 3 (Google) | Inactive (premium) | $0.03 | Activate when billing approved |

No code changes required to swap — set `active: true` in `skills.json`.

---

## Environment Variables by Service

| Service | Key Variables |
|---|---|
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Google (OAuth) | `GOOGLE_DRIVE_TOKEN_JSON`, `GOOGLE_TOKEN_PATH` |
| Google (Service Account) | `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_CREDENTIALS_PATH` |
| Google OAuth App | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| Gemini | `GOOGLE_AI_API_KEY` |
| SerpAPI | `SERPAPI_KEY` |
| Etsy | `ETSY_API_KEY`, `ETSY_API_SECRET`, `ETSY_SHOP_ID`, `ETSY_ACCESS_TOKEN`, `ETSY_REFRESH_TOKEN` |
| Resend | `RESEND_API_KEY`, `EMAIL_FROM` |
| Gmail | `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD` |
| Slack | `SLACK_BOT_TOKEN`, `SLACK_REVIEW_CHANNEL`, `SLACK_ALERTS_CHANNEL` |
| Jira | `JIRA_DOMAIN`, `JIRA_EMAIL`, `JIRA_API_KEY` |
| Pinterest | `PINTEREST_APP_ID`, `PINTEREST_APP_SECRET`, `PINTEREST_ACCESS_TOKEN` |
| Buffer | `BUFFER_ACCESS_TOKEN` |
| Database | `DATABASE_URL` |
| Redis | `REDIS_URL` |
| JWT | `JWT_SECRET` |
| Web app | `ALLOWED_EMAIL`, `CORS_ORIGINS` |
| Frontend | `VITE_API_URL` |
| Cloudflare | `CLOUDFLARE_GLOBAL_API_KEY` |
| Qdrant | `QDRANT_URL`, `QDRANT_API_KEY` |
| xAI Grok | `XAI_API_KEY` (or `GROK_API_KEY` or `X_AI_API_KEY`) |
| Market Research Drive | `DRIVE_MARKET_RESEARCH_ID` |
| Content Studio — Service B | `REPURPOSING_PACK_HUMAN_REVIEW_ALWAYS` (default true), `REPURPOSING_PACK_VIDEO_MAX_MB` (default 500), `FFMPEG_BINARY` (default ffmpeg) |
| LangSmith *(planned)* | `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`, `LANGCHAIN_TRACING_V2` |
