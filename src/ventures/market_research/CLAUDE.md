# Market Research Venture — CLAUDE.md
## Claude Code Context File — Venture Level

**Read `/CLAUDE.md` (root) first for platform architecture rules.**
**This file is authoritative for all work on the Market Research venture.**

---

## What This Venture Is

**Venture E — Market Research**
**Brand:** Plan B AI Platform (internal / white-label)
**Route in admin:** `planBadmin.com/ventures/strategy-room` → Market Research tab

An on-demand multi-LLM market research service. Given a topic, the v2 agentic pipeline:
1. **Decomposes** the topic into 3-4 focused Work Packages (each with named report sections)
2. **Researches** each package: all selected LLMs run in parallel, outputs are Level-1 merged by Claude; a completeness gate fills any missing sections; carry-forward context prevents repetition between packages
3. **Stitches** all package merges into a final report with Executive Summary (Level-2 merge)
4. **Critiques** the report: a configurable critic LLM reviews quality and flags gaps
5. **Renders** a professional PDF (Playwright)
6. **Delivers**: Google Drive upload + optional email

---

## Directory Structure

```
src/ventures/market_research/
  pipeline.py     # Full pipeline: v2 agentic workflow + v1 backwards compat, Celery entry point
  config.py       # System prompts (decomposer, package merge, stitch, critic, optimizer)
  CLAUDE.md       # This file
```

---

## Pipeline Stages

### V2 (new sessions — agentic work-package flow)

| Stage | Status field | What happens |
|---|---|---|
| `optimizing` | Stage 1 | Claude decomposes topic into 3-4 Work Packages; AI title generated (≤10 words) |
| `researching` | Stage 2 | Per-package loop (sequential): all LLMs run in parallel on same scoped prompt (max_tokens=8192) → Level-1 merge → completeness gate → continuation fill if sections missing; carry-forward context passed to next package; each package result persisted for resumability |
| `merging` | Stage 3 | Level-2 stitch: Claude assembles all package merges + writes Executive Summary |
| `reflecting` | Stage 4 | Critic LLM (default: Grok) reviews final report quality |
| `generating_pdf` | Stage 5 | Playwright renders HTML→PDF |
| `pdf_ready` | Stage 6 | Drive upload (non-fatal if unconfigured) |
| `delivering` | Stage 6b | Email sent if `client_email` is set |
| `delivered` | Final | Pipeline complete |

### V1 (backwards compat — rerun mode with pre-set per-LLM prompts)

V1 sessions have `optimized_prompts = {llm_id: prompt_text}` (no `"version"` key). The pipeline detects this and runs the old flow: parallel research → merge → critic. No decomposition.

---

## Prompt Format Versions

| Field | V1 Format | V2 Format |
|---|---|---|
| `optimized_prompts` | `{llm_id: prompt_text}` | `{"version": 2, "packages": [{id, name, scope, sections}]}` |
| `research_results` | `{llm_id: raw_text}` | `{"version": 2, "packages": {pkg_id: {name, scope, sections, merged}}, "total": N}` |

V2 packages are written one at a time as they complete — partial progress survives on retry.

---

## Supported LLMs

| Key | Model | API |
|---|---|---|
| `claude` | claude-sonnet-4-6 | Anthropic |
| `openai` | gpt-4o | OpenAI |
| `gemini` | gemini-2.0-flash-001 | Google Generative AI |
| `grok` | grok-3-mini | xAI (OpenAI-compatible at `https://api.x.ai/v1`) |

Grok key aliases checked in order: `XAI_API_KEY`, `GROK_API_KEY`, `X_AI_API_KEY`.

`available_llms()` in `multi_llm_research.py` dynamically checks which API keys are present at runtime.

---

## RAG Support

Users can upload documents before running a session. Supported formats: PDF, TXT, MD, CSV, DOCX/DOC, XLSX/XLS, PPTX/PPT. Chunks are stored in Qdrant (`market_research_rag` collection, namespaced by `session_id`). The decomposer retrieves relevant context and injects it into package scope prompts.

- Embedding model: `text-embedding-3-small` (OpenAI)
- Graceful degradation: if `QDRANT_URL` is not set, RAG is skipped silently

---

## Database Model

**Table:** `market_research`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | Session ID |
| `topic` | String | Raw user input |
| `title` | String(500) | AI-generated short title (≤10 words) |
| `status` | String | See pipeline stages above |
| `selected_llms` | JSONB | List of LLM keys |
| `critic_llm` | String | Default: `grok` |
| `rag_doc_ids` | JSONB | Qdrant point IDs for uploaded documents |
| `optimized_prompts` | JSONB | v1: `{llm_key: prompt}` / v2: `{version: 2, packages: [...]}` |
| `research_results` | JSONB | v1: `{llm_key: text}` / v2: `{version: 2, packages: {pkg_id: {..., merged}}}` |
| `merged_report` | Text | Level-2 stitched report (v2) or merged report (v1) |
| `critic_feedback` | Text | Critic review output |
| `final_report` | Text | Same as merged_report (critic feedback shown separately in UI) |
| `pdf_path` | String | Local `/tmp/` path |
| `drive_link` | String | Google Drive view link |
| `client_email` | String | Optional email delivery address |
| `error` | Text | Last error message |
| `celery_task_id` | String | For task tracking |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/ventures/market-research/sessions` | Create + queue new session |
| `POST` | `/api/ventures/market-research/sessions/{id}/upload` | Upload RAG documents |
| `GET` | `/api/ventures/market-research/sessions` | List sessions (last 50) |
| `GET` | `/api/ventures/market-research/sessions/{id}` | Session detail |
| `POST` | `/api/ventures/market-research/sessions/{id}/retry` | Re-queue a failed or stuck-pending session |
| `POST` | `/api/ventures/market-research/sessions/{id}/rerun` | Clone session with adjusted v1 prompts |
| `GET` | `/api/ventures/market-research/available-llms` | Which LLMs are configured |

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude (required) |
| `OPENAI_API_KEY` | OpenAI GPT-4o + embeddings for RAG |
| `GOOGLE_AI_API_KEY` | Gemini |
| `XAI_API_KEY` / `GROK_API_KEY` / `X_AI_API_KEY` | xAI Grok (any one) |
| `QDRANT_URL` | Qdrant Cloud endpoint (RAG; optional) |
| `QDRANT_API_KEY` | Qdrant auth (optional) |
| `DRIVE_MARKET_RESEARCH_ID` | Google Drive folder for PDF uploads |

---

## Frontend

**Location:** `frontend/src/pages/StrategyRoom.tsx` → Market Research tab

**Features:**
- LLM selection checkboxes + Critic LLM selector
- RAG document upload (PDF, DOCX, XLSX, PPTX, TXT, CSV)
- Session list showing AI title + status badge
- Session detail drawer with tabs: Report (GFM markdown) / Critic Feedback / Work Packages
- Retry Now: re-queues failed or stuck-pending sessions (pinned footer)
- Adjust & Rerun: available only for v1 sessions — edit per-LLM prompts and clone the session

---

## Key Skills Used

| Skill | Purpose |
|---|---|
| `aiplatform.skills.research.multi_llm_research` | Parallel LLM execution; `max_tokens` param added for package-level 8192 token budget |
| `aiplatform.skills.research.rag_store` | Qdrant ingest + retrieval; Office file extraction added |
| `aiplatform.skills.storage.drive_write` | PDF upload to Drive |
| `aiplatform.skills.comms.send_email` | Optional email delivery |

---

## Architecture Constraints

- The pipeline imports from `aiplatform.*` and `ventures.market_research.*` only (no `src.` prefix — worker adds `src/` to sys.path)
- `multi_llm_research.py` is a platform skill — it knows nothing about market research; the pipeline injects all prompts and system context
- PDF generation uses Playwright (inline in pipeline.py, not the shared `generate_pdf` skill, because the report format is venture-specific)
- Drive upload is non-fatal — if `DRIVE_MARKET_RESEARCH_ID` is not set, the PDF is saved locally and the session still completes
- V2 package results are persisted after each package completes — retrying a failed session resumes from the last completed package
- The completeness gate (`_missing_sections`) detects truncated output by checking for expected `## Heading` markers and triggers a continuation fill call

---

## Pipeline Status

| Feature | Status | Notes |
|---|---|---|
| Multi-LLM parallel research | ✅ live | Claude, OpenAI, Gemini, Grok |
| Agentic work-package pipeline (v2) | ✅ live | 3-4 packages; Level-1 merge per package; Level-2 stitch; completeness gate; carry-forward context; resumable on retry |
| Prompt optimizer (v1 only) | ✅ live | Per-model angle assignment; used only for v1 rerun sessions |
| Merger / stitch | ✅ live | Level-1 package merge + Level-2 stitch with Executive Summary |
| Critic/reflection | ✅ live | Configurable critic LLM (default Grok) |
| PDF generation | ✅ live | Playwright HTML→PDF |
| Drive upload | ✅ live | `DRIVE_MARKET_RESEARCH_ID` folder |
| Email delivery | ✅ live | Includes Drive link + AI title in subject |
| RAG document upload | ✅ live | Qdrant; Office formats (docx, xlsx, pptx) supported; skipped gracefully if Qdrant not configured |
| Markdown report rendering | ✅ live | GFM tables + headings rendered in UI via react-markdown + remark-gfm |
| Retry Now | ✅ live | Re-queues failed or stuck-pending sessions; pinned footer in drawer |
| Adjust & Rerun (v1) | ✅ live | Edit per-LLM prompts and clone session; hidden for v2 sessions |
| AI-generated session title | ✅ live | ≤10 words; used in email subject and session list |
