# Market Research Venture — CLAUDE.md
## Claude Code Context File — Venture Level

**Read `/CLAUDE.md` (root) first for platform architecture rules.**
**This file is authoritative for all work on the Market Research venture.**

---

## What This Venture Is

**Venture E — Market Research**
**Brand:** Plan B AI Platform (internal / white-label)
**Route in admin:** `planBadmin.com/ventures/strategy-room` → Market Research tab

An on-demand multi-LLM market research service. Supports three pipeline versions:

- **V3 (default for new sessions):** User selects from a fixed section library. Each section has its own research prompt, a 2-round author/critic loop, citation enforcement, and reference context from prior sections. Sections are assembled in order into a final document + citations appendix.
- **V2 (backwards compat):** LLM-decomposed work packages, parallel research, Level-1 and Level-2 merge.
- **V1 (backwards compat — rerun mode):** Pre-set per-LLM prompts, parallel research, single merge.

---

## Directory Structure

```
src/ventures/market_research/
  pipeline.py     # Full pipeline: v3 section loop + v2 work packages + v1 rerun, Celery entry point
  config.py       # SECTION_LIBRARY, CROSS_MODULE_SYSTEM_PROMPT, all system prompts
  CLAUDE.md       # This file
```

---

## V3 Pipeline (Default for New Sessions)

### What Triggers V3
A session uses V3 when `record.section_config` is not null. The `section_config` is set by the frontend's section selector when the user enables "Customise sections".

### Flow

```
[User selects sections + edits prompts] → saved as section_config
         ↓
[For each enabled section (sequential)]:
    drafting:    All selected LLMs research section in parallel (8192 tokens each)
    merging:     Level-1 merge of LLM outputs (same as _merge_package)
    reviewing_1: Critic checks (a) required_items present? (b) every quantitative claim cited?
                 → PASS or REVISE with specific gaps
    (if REVISE): Author fills gaps (round 2)
    reviewing_2: Critic reviews again
    (if REVISE): Append disclaimer — section status → "disclaimer"
    (if PASS):   Section status → "done"
    Build 2-sentence summary for reference context of next sections
         ↓
[Assembly]: Python concatenation of all section drafts + citations appendix
         ↓
[PDF + Drive + Email] (unchanged)
```

### Reference Context
Before each section's LLM calls, all completed sections contribute a 2-sentence summary.
Passed as a block: `## Already Covered\n- Section Name: [summary]`.
This prevents repetition and builds cumulative insights.

### Citation Enforcement
LLM prompts require inline citations: `[Source: Name, Year]`.
The critic's checklist includes: "does every quantitative claim have a citation?"
`_extract_citations()` collects all `[Source: ...]` occurrences from each section.
`_build_citations_appendix()` groups them by section for the final document.

### Critic Loop (2 rounds max)
- Round 1: checks `required_items` list + citation coverage → `PASS` or `REVISE`
- If `REVISE`: `_fill_section_gaps()` appends targeted improvements to the draft
- Round 2: same checks on the improved draft
- If still `REVISE`: disclaimer appended, section marked `"disclaimer"`

### Session-Level System Prompt
`section_config.system_prompt` (default: `CROSS_MODULE_SYSTEM_PROMPT`) is injected into every section research call. Instructs LLMs to reference prior modules and avoid contradictions.

---

## Section Library

Defined in `config.py` as `SECTION_LIBRARY: list[dict]`. Default 8 modules + Final Synthesis:

| # | ID | Name | Locked |
|---|---|---|---|
| 1 | `market_regulation` | Market & Regulation | — |
| 2 | `competitor_deep_dive` | Competitor Deep Dive | — |
| 3 | `pricing_business_model` | Pricing & Business Model | — |
| 4 | `ppc_search_economics` | PPC & Search Economics | — |
| 5 | `funnels_landing_pages` | Funnels & Landing Pages | — |
| 6 | `creative_messaging` | Creative & Messaging | — |
| 7 | `product_technology` | Product & Technology | — |
| 8 | `strategy_layer` | Strategy Layer | — |
| 9 | `final_synthesis` | Final Synthesis | 🔒 always last |

`locked: True` sections cannot be disabled in the UI.

To **add a new default section**: add an entry to `SECTION_LIBRARY` in `config.py`. Follow the schema:
```python
{
    "id": "unique_snake_case_id",
    "name": "Display Name",
    "required_items": ["item 1", "item 2"],
    "expected_outputs": ["output 1"],
    "default_prompt": "Full research prompt text…",
    "default_enabled": True,
    "locked": False,
}
```

---

## Pipeline Stages

### V3 Stage Statuses

**Session status** (stored in `record.status`):
`pending → researching → merging → generating_pdf → pdf_ready → delivering → delivered`

**Section status** (stored in `research_results.sections[id].status`):
`pending → drafting → merging → reviewing_1 → reviewing_2 → done | disclaimer`

### V2 Stages (legacy)
`optimizing → researching → merging → reflecting → generating_pdf → pdf_ready → delivering → delivered`

### V1 Stages (rerun mode)
`researching → merging → reflecting → generating_pdf → pdf_ready → delivering → delivered`

---

## Database Model

**Table:** `market_research`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | Session ID |
| `topic` | String | Raw user input |
| `title` | String(500) | AI-generated short title |
| `status` | String | See pipeline stages above |
| `selected_llms` | JSONB | List of LLM keys |
| `critic_llm` | String | Default: `grok` (used in V1/V2; V3 uses Claude for section critic) |
| `rag_doc_ids` | JSONB | Qdrant point IDs for uploaded documents |
| `section_config` | JSONB | **V3:** `{version:3, system_prompt, sections:[{id,name,enabled,prompt,locked,required_items,expected_outputs}]}` |
| `optimized_prompts` | JSONB | V2: `{version:2, packages:[...]}` / V1: `{llm_id: prompt}` |
| `research_results` | JSONB | V3: `{version:3, sections:{id:{status,draft,citations,summary,critic_round_1,critic_round_2}}}` / V2/V1: legacy |
| `merged_report` | Text | Assembled final report (all versions) |
| `critic_feedback` | Text | V3: JSON of per-section critic results; V1/V2: raw critic text |
| `final_report` | Text | Same as merged_report |
| `pdf_path` | String | Local `/tmp/` path |
| `drive_link` | String | Google Drive view link |
| `client_email` | String | Optional email delivery address |
| `error` | Text | Last error message |
| `celery_task_id` | String | For task tracking |

---

## Pipeline Version Detection

```python
if record.section_config:          → _run_v3()
elif optimized_prompts has no "version" key:  → _run_v1()
else:                              → _run_v2()
```

V3 sessions are resumed by skipping sections whose status is already `"done"` or `"disclaimer"`.

---

## Key Pipeline Functions (V3)

| Function | Purpose |
|---|---|
| `_run_v3(record, db, session_id, topic, selected)` | Outer loop over enabled sections |
| `_build_section_research_prompt(section, ref_context, system_prompt)` | Builds per-section LLM prompt with reference context + cross-module instructions |
| `_merge_section(topic, section, llm_results)` | Level-1 merge of all LLM outputs for one section |
| `_critic_section(section, draft)` | Runs critic against required_items + citation check → returns verdict dict |
| `_fill_section_gaps(topic, section, draft, critic_result)` | Author pass: appends targeted improvements |
| `_build_section_summary(section_name, draft)` | Generates 2-sentence summary for reference context |
| `_extract_citations(text)` | Extracts all `[Source: ...]` tags, deduplicated |
| `_build_citations_appendix(section_results)` | Builds Markdown appendix grouped by section |

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/ventures/market-research/sessions` | Create + queue new session (accepts `section_config` for V3) |
| `POST` | `/api/ventures/market-research/sessions/{id}/upload` | Upload RAG documents |
| `GET` | `/api/ventures/market-research/sessions` | List sessions (last 50) |
| `GET` | `/api/ventures/market-research/sessions/{id}` | Session detail (includes `section_config`) |
| `GET` | `/api/ventures/market-research/sessions/{id}/sections/{sec_id}` | Single section detail (V3 only) |
| `GET` | `/api/ventures/market-research/section-library` | Default section library + default system prompt |
| `POST` | `/api/ventures/market-research/sessions/{id}/retry` | Re-queue a failed/stuck session |
| `POST` | `/api/ventures/market-research/sessions/{id}/rerun` | Clone session with adjusted V1 prompts |
| `GET` | `/api/ventures/market-research/available-llms` | Which LLMs are configured |
| `GET` | `/api/ventures/market-research/sessions/{id}/history` | Full job audit snapshot — topic, system prompt, all section prompts, filenames, start/end time, duration, errors, PDF Drive link |

---

## Frontend

**Location:** `frontend/src/pages/StrategyRoom.tsx` → Market Research tab

**V3 UI features:**
- **"Customise sections (V3)" toggle** in the creation form — reveals `SectionSelector` component
- **SectionSelector**: checkbox per section, "Edit prompt" expand per section, "Add section" button for custom sections, editable cross-module system prompt
- **Sections tab** in `SessionDetailDrawer`: grid of section cards with live status badge + word count; clicking opens `SectionDetailPanel`
- **SectionDetailPanel**: section draft (markdown rendered), Critic Round 1 / Round 2 collapsible panels showing missing items and uncited claims
- **Citations tab**: all citations grouped by section, live-updated as sections complete
- **History tab**: lazy-loaded (fetched only when tab is opened); shows run details grid (topic, LLMs, start/end, duration), uploaded filenames, errors, PDF link, collapsible cross-module system prompt, collapsible per-section prompts

**Polling:** existing 4s polling on session detail updates section statuses in real time.

---

## Supported LLMs

| Key | Model | API |
|---|---|---|
| `claude` | claude-sonnet-4-6 | Anthropic |
| `openai` | gpt-4o | OpenAI |
| `gemini` | gemini-2.0-flash-001 | Google Generative AI |
| `grok` | grok-3-mini | xAI |

---

## RAG Support

Same as V2 — Qdrant-backed, injected into section prompts if documents uploaded. Graceful degradation if Qdrant not configured.

---

## Environment Variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude (required — used for section research, merge, critic, summary) |
| `OPENAI_API_KEY` | OpenAI GPT-4o + embeddings for RAG |
| `GOOGLE_AI_API_KEY` | Gemini |
| `XAI_API_KEY` / `GROK_API_KEY` / `X_AI_API_KEY` | xAI Grok (any one) |
| `QDRANT_URL` | Qdrant Cloud endpoint (RAG; optional) |
| `QDRANT_API_KEY` | Qdrant auth (optional) |
| `DRIVE_MARKET_RESEARCH_ID` | Google Drive folder for PDF uploads |

---

## Architecture Constraints

- `_run_v3()` never calls V2/V1 functions — they are fully separate code paths
- The section critic always uses Claude (`_claude_sync`) — it needs structured JSON output; Grok is not reliable for this
- `section_config` is set at session creation and never mutated during the pipeline
- V3 has no `reflecting` status — the per-section critic replaces the final-pass critic
- The citations appendix is built from `[Source: ...]` regex matches — authors are instructed to use this exact format in all section prompts
- PDF generation reads `final_report` which equals `merged_report` for V3 (same concatenated output)

---

## Pipeline Status

| Feature | Status | Notes |
|---|---|---|
| Multi-LLM parallel research | ✅ live | Claude, OpenAI, Gemini, Grok |
| V3 section-based pipeline | ✅ built | 8 sections + Final Synthesis; 2-round critic loop; citation enforcement; reference context |
| Section library | ✅ built | 9 default sections in config.py; user-editable prompts; custom section support |
| V2 agentic work-package pipeline | ✅ live | Backwards compat |
| V1 rerun mode | ✅ live | Backwards compat |
| Critic/reflection (V3) | ✅ built | Per-section; checks required_items + citations; 2 rounds max; disclaimer fallback |
| Citation enforcement | ✅ built | Inline `[Source: ...]` tags; citations appendix in final doc |
| Reference context (cross-module) | ✅ built | 2-sentence summaries passed to each subsequent section |
| Section-level status UI | ✅ built | Cards with live status badges; word count; click to open SectionDetailPanel |
| Citations tab | ✅ built | All citations grouped by section in drawer |
| PDF generation | ✅ live | Playwright HTML→PDF |
| Drive upload | ✅ live | `DRIVE_MARKET_RESEARCH_ID` folder |
| Email delivery | ✅ live | Includes Drive link |
| RAG document upload | ✅ live | Qdrant; Office formats; graceful degradation |
| Retry Now | ✅ live | V3 resumes from last completed section |
| Job history endpoint | ✅ built | GET /sessions/{id}/history — full audit snapshot with prompts, timing, files, PDF link |
| History tab (frontend) | ✅ built | Lazy-loaded tab in SessionDetailDrawer; collapsible system/section prompts |
| started_at / completed_at / uploaded_filenames | ✅ built | DB columns + migration c2d3e4f5a6b7; pipeline sets timestamps on start/end/error |
