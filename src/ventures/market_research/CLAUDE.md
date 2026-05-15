# Market Research — CLAUDE.md
## Claude Code Context File — Venture Level

**Read `/CLAUDE.md` (root) first for platform architecture rules.**
**This file is authoritative for all work on the Market Research venture.**

---

## Product Identity

**Product:** Market Research (Venture E)
**Order surfaces:**
- `planBadmin.com` Strategy Room → Market Research tab (current)
- Future: standalone website (not EchoForge.biz) — submits orders via `POST /api/ventures/market-research/sessions` with API-key auth

**Architecture:** productized, multi-sector, configurable research engine. Not EchoForge-specific.

**Sector registry:** `registry.py` — defines all sectors and their section libraries. Adding a new sector = one entry in `SECTORS` dict, no pipeline changes.

**Report configuration:** `report_config` JSONB on the `market_research` record controls output depth, writing style, analytical framework, and citation format per session.

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
  config.py       # Re-exports SECTION_LIBRARY + CROSS_MODULE_SYSTEM_PROMPT from registry.py; all system prompts
  registry.py     # PRODUCTS + SECTORS dict (all 4 sector section libraries); build_report_directives()
  CLAUDE.md       # This file
```

---

## Product Registry (`registry.py`)

### Two-level hierarchy: Product → Sector → Section Library

```python
PRODUCTS = {
    "market_research": {
        "display_name": "Market Research",
        "sectors": ["business_intelligence", "academic", "vc_due_diligence", "product_discovery"],
        "default_sector": "business_intelligence",
    }
}
```

Each entry in `SECTORS` has:
- `display_name`, `description` — shown in UI sector picker
- `section_library: list[dict]` — same schema as the current `SECTION_LIBRARY`
- `default_system_prompt: str` — pre-filled in the cross-module system prompt editor
- `terminology_overrides: dict` — reserved for UI label overrides

### How to add a new sector

1. Add an entry to `SECTORS` in `registry.py` with `section_library`, `default_system_prompt`, and display fields
2. No pipeline changes needed — the sector's section_library is loaded via the API and stored in `section_config`
3. Add the sector key to the `PRODUCTS["market_research"]["sectors"]` list

### Current sectors

| Key | Display Name | Locked Final Section | Notes |
|---|---|---|---|
| `business_intelligence` | Business Intelligence | Final Synthesis | Default sector |
| `academic` | Academic & Research | Executive Abstract | |
| `product_discovery` | Product Discovery | Product Executive Summary | |
| `legal_research` | Legal Research | Legal Summary & Recommendations | Jurisdiction mandatory in topic |
| `medical_research` | Medical & Health Research | Clinical Summary & Recommendations | Peer-reviewed sources only |

**VC Due Diligence** was removed from the active sector list. The section library code (`_VC_SECTION_LIBRARY`, `_VC_SYSTEM_PROMPT`) is preserved in `registry.py` as dead code for easy re-activation.

### Online Search Requirement

All sector system prompts include `_ONLINE_SEARCH_INSTRUCTION`, which instructs all LLMs:
- Do not rely on pre-training data alone
- Actively search for publications, studies, and data from the last 12-24 months
- Mark any claim that cannot be verified with a recent source as `[Pre-training data — currency unverified]`

---

## Report Configuration (`report_config`)

Stored as JSONB on the `market_research` record. Set at session creation; never mutated by the pipeline.

```json
{
  "output_depth":    "executive" | "standard" | "exhaustive",
  "writing_style":   "corporate" | "academic" | "aggressive" | "online_explainer",
  "framework":       "swot" | "pestle" | "lean_canvas" | "porters" | "none",
  "citation_format": "inline" | "apa" | "mla" | "hyperlink"
}
```

**Token budget** (`registry.py → DEPTH_MAX_TOKENS`) — controls max_tokens per LLM call per section:
- `executive`: 4096 tokens → approx **5-10 page report / ~3,000 words total**
- `standard`: 8192 (default) → approx **20-35 page report / ~12,000 words total**
- `exhaustive`: 16384 → approx **50-80 page report / ~30,000 words total**

**Injection point:** `_build_section_research_prompt()` in `pipeline.py` calls `build_report_directives(report_config)` and appends the resulting `## Report Directives` block to every section prompt.

**`build_report_directives()`** in `registry.py` converts the config dict into a human-readable directives block. Returns empty string if `report_config` is None (preserves current default behaviour).

### Writing Styles — What Each Does

| Style | Tone | Use Case | What Changes in Output |
|---|---|---|---|
| `corporate` | Direct, professional, McKinsey-style | Client deliverables, management reports | Active voice, bullet-point summaries, decisive recommendations, no hedging |
| `academic` | Formal, hedging, objective | University, research, professional papers | Passive voice, language like "evidence suggests", no superlatives, APA-style structure |
| `aggressive` | High-energy, growth-focused, provocative | VC pitches, startup strategy | Bold openers, startup vernacular ("land-grab", "dominate"), confident assertions, opportunity-first framing |
| `online_explainer` | Conversational, accessible, structured | Video scripts, how-to articles, blog posts | Short paragraphs (2-3 sentences), numbered steps, plain English, rhetorical questions, zero passive voice — ready to use as a script with minimal editing |

### Analytical Frameworks — What Each Does

Frameworks are injected as an additional analytical lens over the research. They do not replace section prompts; they add a structured perspective the LLMs must apply where relevant.

| Framework | What It Does to the Report |
|---|---|
| `none` | No framework overlay — sections follow their own structure |
| `swot` | Every strategic assessment is organised through Strengths / Weaknesses / Opportunities / Threats. Adds SWOT matrices to relevant sections. |
| `pestle` | Market and environmental analysis is filtered through Political / Economic / Social / Technological / Legal / Environmental dimensions. Useful for macro-level market reports and regulatory-heavy topics. |
| `lean_canvas` | Analysis is framed around the Lean Canvas model: Problem, Solution, Unique Value Proposition, Unfair Advantage, Customer Segments, Key Metrics, Channels, Cost Structure, Revenue Streams. Best for product and startup research. |
| `porters` | Competitive analysis uses Porter's Five Forces: Threat of New Entrants, Supplier Power, Buyer Power, Threat of Substitutes, Competitive Rivalry. Best for market entry or competitive strategy reports. |

### Citation Formats — What Each Produces

| Format | What It Looks Like in the Report | Best For |
|---|---|---|
| `inline` | `[Source: McKinsey, 2024]` after every claim | Internal reports, quick reads |
| `apa` | `(McKinsey, 2024)` in-text + full reference list at the end (`McKinsey & Company. (2024). Title.`) | Academic papers, formal reports |
| `mla` | `(McKinsey 42)` in-text + Works Cited list at the end | Humanities, literature-heavy research |
| `hyperlink` | `[Source: Report Title](https://url.com)` — clickable links embedded in text | Digital reports, web-published content, when sources have stable URLs |

---

## Order Surface: planBadmin

**Creation form** (`frontend/src/pages/StrategyRoom.tsx`):
- **Research Type** selector — loads sector section library via `GET /api/ventures/market-research/products`
- **Report Format** panel — Output Depth, Writing Style, Framework, Citation Format controls
- `report_config` and `sector` are included in the `POST /api/ventures/market-research/sessions` payload

---

## Order Surface: External Website (Phase 3)

The future standalone website (not EchoForge.biz) POSTs to the same API with API-key auth:
- Header: `X-API-Key: {MARKET_RESEARCH_API_KEY}` (env var on Railway)
- Optional `callback_url` in the request body → pipeline fires a webhook on completion
- No Google OAuth required for external submissions

**Contract:** `POST /api/ventures/market-research/sessions`
```json
{
  "topic": "AI accessibility tools market",
  "sector": "business_intelligence",
  "report_config": {"output_depth": "standard", "writing_style": "corporate"},
  "selected_llms": ["claude", "openai"],
  "client_email": "client@example.com",
  "section_config": { ... }
}
```

---

## Roadmap

| Phase | Goal | Status |
|---|---|---|
| Phase 1 | Report format controls (depth/style/framework/citation) for BI sector | ✅ built |
| Phase 2 | New sectors: Academic, Product Discovery, Legal, Medical; online_explainer style; online search instruction; page-count depth estimates | ✅ built |
| Phase 3 | External website order surface (API-key auth, webhook callback) | 🔲 planned |
| Phase 4 | URL + PDF data ingestion as research source; whitepaper depth (50+ pages) | 🔲 planned |

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
| `GET` | `/api/ventures/market-research/products` | Product + sector registry for UI sector picker |
| `GET` | `/api/ventures/market-research/sector-library/{sector}` | Section library + system prompt for a specific sector |

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
- **Styled tables:** `CROSS_MODULE_SYSTEM_PROMPT` instructs all LLMs to use Markdown table syntax (`| col | col |` with separator row). `_build_pdf()` uses `render_markdown.py` to convert Markdown tables to styled HTML `<table>` elements (blue `#1e3a5f` header, alternating rows, `break-inside: avoid`) — no ASCII art reaches the PDF.
- **Visual content:** LLMs may embed `[SCREENSHOT: url | caption]` or `[GENERATE IMAGE: description | caption]` markers. At PDF build time, `_build_pdf()` scans for markers, captures each (Playwright screenshot or Gemini Imagen chart), base64-encodes as data URIs, and passes to `render_markdown.py` for `<figure>` embedding. Markers with failed captures are silently dropped.
- `render_markdown.py` and `capture_visual.py` are venture-agnostic platform skills — they live in `/aiplatform/skills/media/` and are not Market Research-specific.

---

## Pipeline Status

| Feature | Status | Notes |
|---|---|---|
| Multi-LLM parallel research | ✅ live | Claude, OpenAI, Gemini, Grok |
| V3 section-based pipeline | ✅ built | 8 sections + Final Synthesis; 2-round critic loop; citation enforcement; reference context |
| Section library | ✅ built | 9 default sections in config.py (re-exported from registry.py); user-editable prompts; custom section support |
| Product + Sector registry | ✅ built | registry.py — 4 sectors (BI, Academic, VC, PM Discovery); PRODUCTS dict; build_report_directives() |
| Report configuration (depth/style/framework/citation) | ✅ built | report_config JSONB on record; injected into section prompts via build_report_directives(); token budget scales with output_depth |
| New sector section libraries | ✅ built | Academic, VC Due Diligence, Product Discovery — in registry.py |
| Sector library endpoints | ✅ built | GET /sector-library/{sector}; GET /products |
| V2 agentic work-package pipeline | ✅ live | Backwards compat |
| V1 rerun mode | ✅ live | Backwards compat |
| Critic/reflection (V3) | ✅ built | Per-section; checks required_items + citations; 2 rounds max; disclaimer fallback |
| Citation enforcement | ✅ built | Inline `[Source: ...]` tags; citations appendix in final doc |
| Reference context (cross-module) | ✅ built | 2-sentence summaries passed to each subsequent section |
| Executive Summary | ✅ built | Generated post-loop from per-section key_takeaways; inserted first in assembled doc |
| Table of Contents | ✅ built | Programmatic TOC from section list at assembly time; includes Citations entry |
| Section-level status UI | ✅ built | Cards with live status badges; word count; click to open SectionDetailPanel |
| Citations tab | ✅ built | All citations grouped by section in drawer |
| PDF generation | ✅ live | Playwright HTML→PDF |
| Styled HTML tables in PDF | ✅ live | render_markdown.py converts Markdown tables to styled HTML |
| Visual content in PDF | ✅ live | capture_visual.py (Playwright screenshots + Gemini Imagen charts); markers resolved to base64 data URIs at PDF build time |
| Drive upload | ✅ live | `DRIVE_MARKET_RESEARCH_ID` folder |
| Email delivery | ✅ live | Includes Drive link |
| RAG document upload | ✅ live | Qdrant; Office formats; graceful degradation |
| Retry Now | ✅ live | V3 resumes from last completed section |
| Job history endpoint | ✅ built | GET /sessions/{id}/history — full audit snapshot with prompts, timing, files, PDF link |
| History tab (frontend) | ✅ built | Lazy-loaded tab in SessionDetailDrawer; collapsible system/section prompts |
| started_at / completed_at / uploaded_filenames | ✅ built | DB columns + migration c2d3e4f5a6b7; pipeline sets timestamps on start/end/error |
| External website order surface (API-key auth) | 🔲 planned | Phase 3 — X-API-Key header + callback_url webhook |
