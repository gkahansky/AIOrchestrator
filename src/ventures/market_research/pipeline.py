"""
Market Research pipeline.

Stages:
  1. optimizing  — LLM generates tailored prompts per research angle
  2. researching — parallel LLM research committee executes concurrently
  3. merging     — merge model synthesises all outputs into one report
  4. reflecting  — critic model reviews quality and flags gaps
  5. generating_pdf — WeasyPrint PDF built from final report
  6. pdf_ready   — Drive upload + optional email delivery
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from aiplatform.database.models import MarketResearch
from aiplatform.skills.research.multi_llm_research import (
    run_parallel_research_sync,
    available_llms,
    _call_claude,
)
from aiplatform.skills.research.rag_store import retrieve_context
from aiplatform.skills.storage.drive_write import drive_write
from aiplatform.skills.comms.send_email import send_email
from ventures.market_research.config import (
    RESEARCH_ANGLES,
    PROMPT_OPTIMIZER_SYSTEM,
    MERGE_SYSTEM,
    CRITIC_SYSTEM,
)

import anthropic
import asyncio

logger = logging.getLogger(__name__)


def _set_status(db: Session, record: MarketResearch, status: str) -> None:
    record.status = status
    record.updated_at = datetime.now(timezone.utc)
    db.commit()


def _claude_sync(system: str, user: str, max_tokens: int = 4096) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


# ── Stage 1: Prompt Optimizer ──────────────────────────────────────────────────

def _optimize_prompts(topic: str, selected_llms: list[str], session_id: str) -> dict[str, str]:
    """Ask Claude to generate a tailored research prompt per LLM / angle."""
    angles = {
        llm: RESEARCH_ANGLES[i % len(RESEARCH_ANGLES)]
        for i, llm in enumerate(selected_llms)
    }

    rag_context = retrieve_context(topic, session_id)
    rag_note = f"\n\nAdditional context from uploaded documents:\n{rag_context}" if rag_context else ""

    user_msg = (
        f"Research topic: {topic}{rag_note}\n\n"
        f"LLM assignments (model → research angle):\n"
        + "\n".join(f"  {llm}: {angle}" for llm, angle in angles.items())
        + f"\n\nOutput JSON with keys: {json.dumps(selected_llms)}.\n"
        "Each value is the full research prompt that model should execute."
    )

    raw = _claude_sync(PROMPT_OPTIMIZER_SYSTEM, user_msg, max_tokens=2048)

    # Extract JSON from response
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        # Fallback: same prompt for all
        fallback = f"Research the following topic focusing on your assigned angle:\n\nTopic: {topic}"
        return {llm: fallback for llm in selected_llms}

    prompts = json.loads(raw[start:end])
    return {llm: prompts.get(llm, user_msg) for llm in selected_llms}


# ── Stage 2: Parallel Research ─────────────────────────────────────────────────

RESEARCH_SYSTEM = (
    "You are an expert market researcher. Conduct thorough research on the assigned topic "
    "and angle. Provide data-backed insights, specific examples, and concrete numbers where "
    "possible. Structure your response with clear sections."
)


# ── Stage 3: Merge ─────────────────────────────────────────────────────────────

def _merge_reports(topic: str, results: dict[str, str]) -> str:
    sections = "\n\n".join(
        f"=== {llm.upper()} RESEARCH ===\n{text}"
        for llm, text in results.items()
    )
    user_msg = f"Topic: {topic}\n\nParallel research outputs to merge:\n\n{sections}"
    return _claude_sync(MERGE_SYSTEM, user_msg, max_tokens=6000)


# ── Stage 4: Critic / Reflection ───────────────────────────────────────────────

def _critic_review(topic: str, merged: str, critic_llm: str, optimized_prompts: dict) -> str:
    """Run the critic model. Falls back to Claude if critic LLM unavailable."""
    avail = set(available_llms())
    if critic_llm not in avail:
        logger.warning("Critic LLM %s unavailable, falling back to claude", critic_llm)
        critic_llm = "claude"

    user_msg = (
        f"Original research topic: {topic}\n\n"
        f"Merged report to review:\n{merged}"
    )

    from aiplatform.skills.research.multi_llm_research import (
        _call_claude, _call_openai, _call_gemini, _call_grok,
    )
    callers = {
        "claude": _call_claude,
        "openai": _call_openai,
        "gemini": _call_gemini,
        "grok":   _call_grok,
    }
    caller = callers.get(critic_llm, _call_claude)
    return asyncio.run(caller(user_msg, CRITIC_SYSTEM, 90))


# ── Stage 5: PDF Generation ────────────────────────────────────────────────────

def _build_pdf(record: MarketResearch, output_path: str) -> str:
    """Render the report HTML to PDF using Playwright. Returns the pdf path."""
    topic = record.topic
    report = record.final_report or record.merged_report or ""
    critic = record.critic_feedback or ""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Convert plain-text report to basic HTML paragraphs
    def _to_html(text: str) -> str:
        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("# "):
                lines.append(f"<h1>{stripped[2:]}</h1>")
            elif stripped.startswith("## "):
                lines.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("### "):
                lines.append(f"<h3>{stripped[4:]}</h3>")
            else:
                lines.append(f"<p>{stripped}</p>")
        return "\n".join(lines)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Georgia, serif; margin: 40px; color: #1a1a1a; line-height: 1.7; }}
  h1 {{ color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }}
  h2 {{ color: #1e3a5f; margin-top: 32px; }}
  h3 {{ color: #374151; }}
  p  {{ margin: 0.6em 0; }}
  .meta {{ color: #6b7280; font-size: 0.9em; margin-bottom: 24px; }}
  .critic {{ background: #f0fdf4; border-left: 4px solid #22c55e; padding: 12px 16px;
             margin: 24px 0; border-radius: 4px; font-size: 0.92em; }}
  .critic h3 {{ margin: 0 0 8px; color: #15803d; }}
  footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid #e5e7eb;
            color: #9ca3af; font-size: 0.85em; text-align: center; }}
</style>
</head>
<body>
<h1>Market Research Report</h1>
<div class="meta">Topic: <strong>{topic}</strong> &nbsp;|&nbsp; Generated: {now}</div>
{_to_html(report)}
<div class="critic">
<h3>Critic Review</h3>
{_to_html(critic)}
</div>
<footer>Confidential &mdash; Generated by Plan B AI Platform</footer>
</body>
</html>"""

    from pathlib import Path
    from playwright.sync_api import sync_playwright
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-dev-shm-usage", "--no-sandbox"])
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(path=str(out), print_background=True, format="A4",
                 margin={"top": "0.6in", "bottom": "0.6in", "left": "0.5in", "right": "0.5in"})
        browser.close()

    return str(out)


# ── Main Pipeline ──────────────────────────────────────────────────────────────

def run_market_research(research_id: str, db: Session) -> None:
    """
    Full market research pipeline. Called by the Celery worker.
    Updates the MarketResearch record at each stage.
    """
    record = db.get(MarketResearch, uuid.UUID(research_id))
    if not record:
        logger.error("MarketResearch %s not found", research_id)
        return

    session_id  = research_id
    topic       = record.topic
    selected    = record.selected_llms or available_llms()
    critic_llm  = record.critic_llm or "grok"

    try:
        # Stage 1 — Optimize prompts (skip if already provided, e.g. rerun with adjusted prompts)
        if record.optimized_prompts:
            prompts = record.optimized_prompts
            logger.info("run_market_research: using pre-set optimized prompts (rerun mode)")
        else:
            _set_status(db, record, "optimizing")
            prompts = _optimize_prompts(topic, selected, session_id)
            record.optimized_prompts = prompts
            db.commit()

        # Stage 2 — Parallel research
        _set_status(db, record, "researching")
        outcome = run_parallel_research_sync(
            prompts=prompts,
            system_prompt=RESEARCH_SYSTEM,
            selected_llms=selected,
            timeout=180,
        )
        results = outcome["results"]
        if not results:
            raise RuntimeError(f"All LLMs failed: {outcome['errors']}")
        record.research_results = results
        db.commit()

        # Stage 3 — Merge
        _set_status(db, record, "merging")
        merged = _merge_reports(topic, results)
        record.merged_report = merged
        db.commit()

        # Stage 4 — Critic reflection
        _set_status(db, record, "reflecting")
        feedback = _critic_review(topic, merged, critic_llm, prompts)
        record.critic_feedback = feedback
        record.final_report = merged  # final = merged (critic feedback shown separately)
        db.commit()

        # Stage 5 — PDF
        _set_status(db, record, "generating_pdf")
        filename = f"market_research_{research_id[:8]}.pdf"
        output_path = f"/tmp/{filename}"
        pdf_path = _build_pdf(record, output_path)

        # Stage 6 — Drive upload (optional — skipped if no folder ID configured)
        record.pdf_path = pdf_path
        folder_id = os.environ.get("MARKET_RESEARCH_DRIVE_FOLDER_ID") or os.environ.get("GOOGLE_DRIVE_AUDIT_ROOT_ID", "")
        if folder_id:
            try:
                result = drive_write(
                    local_path=pdf_path,
                    folder_id=folder_id,
                    mime_type="application/pdf",
                    filename=filename,
                    share_anyone_with_link=True,
                )
                record.drive_link = result.get("view_link") or result.get("web_view_link", "")
            except Exception as drive_exc:
                logger.warning("Drive upload failed (non-fatal): %s", drive_exc)
        else:
            logger.info("No Drive folder configured — PDF saved locally only: %s", pdf_path)
        _set_status(db, record, "pdf_ready")

        # Optional email delivery
        if record.client_email:
            _set_status(db, record, "delivering")
            send_email(
                to=record.client_email,
                subject=f"Your Market Research Report: {topic}",
                body=(
                    f"Your market research report on '{topic}' is ready.\n\n"
                    f"Download: {drive_link}\n\n"
                    "— Plan B AI Platform"
                ),
            )
            _set_status(db, record, "delivered")
        else:
            _set_status(db, record, "delivered")

    except Exception as exc:
        logger.exception("Market research pipeline failed for %s", research_id)
        record.error = str(exc)
        _set_status(db, record, "failed")
        raise
