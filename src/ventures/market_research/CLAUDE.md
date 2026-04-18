# Market Research Venture — CLAUDE.md
## Claude Code Context File — Venture Level

**Read `/CLAUDE.md` (root) first for platform architecture rules.**
**This file is authoritative for all work on the Market Research venture.**

---

## What This Venture Is

**Venture E — Market Research**
**Brand:** Plan B AI Platform (internal / white-label)
**Route in admin:** `planBadmin.com/ventures/strategy-room` → Market Research tab

An on-demand multi-LLM market research service. Given a topic, the pipeline:
1. Generates tailored research prompts per model/angle (optimizer)
2. Runs a parallel LLM research committee (Claude + OpenAI + Gemini + Grok)
3. Synthesises all outputs into a unified report (merger)
4. Runs a critic pass for quality and gap flags (reflector)
5. Renders a professional PDF report
6. Uploads to Google Drive and optionally emails the report

---

## Directory Structure

```
src/ventures/market_research/
  pipeline.py     # Full pipeline: stages 1–6, Celery entry point
  config.py       # System prompts, research angles, constants
  CLAUDE.md       # This file
```

---

## Pipeline Stages

| Stage | Status field | What happens |
|---|---|---|
| `optimizing` | Stage 1 | Claude generates per-LLM research prompts; AI title generated (≤10 words) |
| `researching` | Stage 2 | All selected LLMs run in parallel (`asyncio`); timeout 180s |
| `merging` | Stage 3 | Claude Sonnet synthesises all results into one report |
| `reflecting` | Stage 4 | Critic LLM (default: Grok) reviews quality and flags gaps |
| `generating_pdf` | Stage 5 | Playwright renders HTML→PDF |
| `pdf_ready` | Stage 6 | Drive upload + optional email delivery |
| `delivering` | Stage 6b | Email sent if `client_email` is set on the record |

**Rerun mode:** if `optimized_prompts` is already set on the record (via the Adjust & Rerun UI), Stage 1 is skipped.

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

Users can upload documents before running a session. These are chunked and stored in Qdrant (`market_research_rag` collection, namespaced by `session_id`). The optimizer retrieves relevant context and injects it into each research prompt.

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
| `optimized_prompts` | JSONB | `{llm_key: prompt_text}` |
| `research_results` | JSONB | `{llm_key: raw_output}` |
| `merged_report` | Text | Merged synthesis |
| `critic_feedback` | Text | Critic review output |
| `final_report` | Text | Same as merged_report (critic shown separately) |
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
| `POST` | `/api/ventures/market-research/sessions/{id}/rerun` | Clone session with adjusted prompts |
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
- LLM selection checkboxes
- Critic LLM selector
- RAG document upload
- Session list showing AI title + status badge
- Session detail drawer with tabs: Report / Critic Feedback / Optimized Prompts
- Adjust & Rerun: edit any optimized prompt and clone the session

---

## Key Skills Used

| Skill | Purpose |
|---|---|
| `aiplatform.skills.research.multi_llm_research` | Parallel LLM execution |
| `aiplatform.skills.research.rag_store` | Qdrant ingest + retrieval |
| `aiplatform.skills.storage.drive_write` | PDF upload to Drive |
| `aiplatform.skills.comms.send_email` | Optional email delivery |

---

## Architecture Constraints

- The pipeline imports from `aiplatform.*` and `ventures.market_research.*` only (no `src.` prefix — worker adds `src/` to sys.path)
- `multi_llm_research.py` is a platform skill — it knows nothing about market research; the pipeline injects all prompts and system context
- PDF generation uses Playwright (inline in pipeline.py, not the shared `generate_pdf` skill, because the report format is venture-specific)
- Drive upload is non-fatal — if `DRIVE_MARKET_RESEARCH_ID` is not set, the PDF is saved locally and the session still completes

---

## Pipeline Status

| Feature | Status | Notes |
|---|---|---|
| Multi-LLM parallel research | ✅ live | Claude, OpenAI, Gemini, Grok |
| Prompt optimizer (Stage 1) | ✅ live | Per-model angle assignment |
| Merger (Stage 3) | ✅ live | Claude Sonnet synthesis |
| Critic/reflection (Stage 4) | ✅ live | Configurable critic LLM |
| PDF generation | ✅ live | Playwright HTML→PDF |
| Drive upload | ✅ live | `DRIVE_MARKET_RESEARCH_ID` folder |
| Email delivery | ✅ live | Includes Drive link + AI title in subject |
| RAG document upload | ✅ live | Qdrant; gracefully skipped if not configured |
| Adjust & Rerun UI | ✅ live | Edit optimized prompts, clone session |
| AI-generated session title | ✅ live | ≤10 words, used in email subject and session list |
