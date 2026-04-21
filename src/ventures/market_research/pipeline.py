"""
Market Research pipeline — v2 Agentic Workflow.

Stages:
  1. optimizing    — Claude decomposes topic into 3-4 Work Packages
  2. researching   — per-package: parallel LLM research → Level-1 merge → completeness gate
  3. merging       — Level-2 stitch: assemble all package merges into final report
  4. reflecting    — critic LLM reviews quality and flags gaps
  5. generating_pdf — Playwright HTML→PDF
  6. pdf_ready     — Drive upload + optional email delivery

Backwards compatible with v1 sessions (pre-decomposed per-LLM prompts from rerun mode).
Resumable: completed packages are skipped when a session is retried.
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
)
from aiplatform.skills.research.rag_store import retrieve_context
from aiplatform.skills.storage.drive_write import drive_write
from aiplatform.skills.comms.send_email import send_email
from ventures.market_research.config import (
    RESEARCH_ANGLES,
    PROMPT_OPTIMIZER_SYSTEM,
    MERGE_SYSTEM,
    CRITIC_SYSTEM,
    PACKAGE_DECOMPOSER_SYSTEM,
    PACKAGE_MERGE_SYSTEM,
    STITCH_SYSTEM,
)

import anthropic
import asyncio

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

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


def _generate_title(topic: str) -> str:
    raw = _claude_sync(
        "You are a research librarian. Respond with ONLY a short title (maximum 10 words, "
        "no punctuation at the end) that clearly summarises the research topic provided. "
        "No preamble, no quotes — just the title.",
        f"Research topic: {topic}",
        max_tokens=64,
    )
    return raw.strip().strip('"').strip("'")[:200]


# ── V1 pipeline (backwards compatibility — rerun mode with per-LLM prompts) ───

RESEARCH_SYSTEM = (
    "You are an expert market researcher. Conduct thorough research on the assigned topic "
    "and angle. Provide data-backed insights, specific examples, and concrete numbers where "
    "possible. Structure your response with clear sections."
)


def _optimize_prompts(topic: str, selected_llms: list[str], session_id: str) -> dict[str, str]:
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
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        fallback = f"Research the following topic focusing on your assigned angle:\n\nTopic: {topic}"
        return {llm: fallback for llm in selected_llms}
    prompts = json.loads(raw[start:end])
    return {llm: prompts.get(llm, user_msg) for llm in selected_llms}


def _merge_reports(topic: str, results: dict[str, str]) -> str:
    sections = "\n\n".join(
        f"=== {llm.upper()} RESEARCH ===\n{text}"
        for llm, text in results.items()
    )
    user_msg = f"Topic: {topic}\n\nParallel research outputs to merge:\n\n{sections}"
    return _claude_sync(MERGE_SYSTEM, user_msg, max_tokens=6000)


def _critic_review(topic: str, merged: str, critic_llm: str) -> str:
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


def _run_v1(
    record: MarketResearch, db: Session, session_id: str,
    topic: str, selected: list[str], critic_llm: str,
    prompts: dict[str, str],
) -> None:
    """V1 pipeline: per-LLM prompts already set (rerun mode) → parallel research → merge → critic."""
    logger.info("run_market_research: v1 mode")
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

    _set_status(db, record, "merging")
    merged = _merge_reports(topic, results)
    record.merged_report = merged
    db.commit()

    _set_status(db, record, "reflecting")
    feedback = _critic_review(topic, merged, critic_llm)
    record.critic_feedback = feedback
    record.final_report = merged
    db.commit()


# ── V2 pipeline: Work Packages ─────────────────────────────────────────────────

def _decompose_packages(topic: str, session_id: str) -> list[dict]:
    rag_context = retrieve_context(topic, session_id)
    rag_note = f"\n\nContext from uploaded documents:\n{rag_context}" if rag_context else ""
    user_msg = f"Research topic: {topic}{rag_note}\n\nDecompose into 3-4 focused work packages."
    raw = _claude_sync(PACKAGE_DECOMPOSER_SYSTEM, user_msg, max_tokens=1024)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return [{
            "id": "pkg_1",
            "name": "Full Research",
            "scope": f"Comprehensive market research on: {topic}",
            "sections": [
                "## Market Overview", "## Market Size & TAM/SAM/SOM",
                "## Competitive Landscape", "## Target Customer Segments",
                "## Market Trends & Emerging Risks", "## Strategic Recommendations",
            ],
        }]
    data = json.loads(raw[start:end])
    return data.get("packages", [])


def _build_package_prompt(package: dict, carry_forward: str = "") -> str:
    sections_list = "\n".join(f"- {s}" for s in package["sections"])
    carry = (
        f"\n\nContext already covered in prior sections (do NOT repeat these points):\n"
        f"...{carry_forward}"
        if carry_forward else ""
    )
    return (
        f"Research scope: {package['scope']}\n\n"
        f"Write the following report sections in full:\n{sections_list}\n\n"
        f"Requirements:\n"
        f"- Use the exact ## section headers listed above\n"
        f"- Provide specific data: named companies, USD figures, CAGR %, market sizes\n"
        f"- Cover every section completely — do not skip or abbreviate any section\n"
        f"- Minimum 300 words per section{carry}"
    )


def _missing_sections(text: str, expected_headers: list[str]) -> list[str]:
    text_lower = text.lower()
    return [
        h for h in expected_headers
        if h.lstrip("#").strip().lower() not in text_lower
    ]


def _continue_truncated(topic: str, package: dict, partial_text: str, missing_sections: list[str]) -> str:
    sections_needed = "\n".join(f"- {s}" for s in missing_sections)
    system = (
        "You are a market research writer completing a partially written report. "
        "Write ONLY the missing sections listed — complete, detailed, with specific data. "
        "Do not repeat or summarise existing content. Use ## Heading format for each section."
    )
    user_msg = (
        f"Topic: {topic}\nPackage: {package['name']}\n"
        f"Scope: {package['scope']}\n\n"
        f"Missing sections to write:\n{sections_needed}\n\n"
        f"Existing text (context — do not repeat):\n...{partial_text[-1500:]}"
    )
    return _claude_sync(system, user_msg, max_tokens=4096)


def _merge_package(topic: str, package: dict, llm_results: dict[str, str]) -> str:
    sections_list = "\n".join(f"- {s}" for s in package["sections"])
    outputs = "\n\n".join(
        f"=== {llm.upper()} ===\n{text}"
        for llm, text in llm_results.items()
    )
    user_msg = (
        f"Topic: {topic}\n"
        f"Package: {package['name']} — {package['scope']}\n"
        f"Required sections:\n{sections_list}\n\n"
        f"LLM outputs to synthesise:\n\n{outputs}"
    )
    return _claude_sync(PACKAGE_MERGE_SYSTEM, user_msg, max_tokens=8192)


def _generate_executive_summary(topic: str, pkg_store: dict) -> str:
    """
    Generate a focused Executive Summary from excerpts of all package merges.
    This is the ONLY LLM call in the assembly stage — keeps it small and reliable.
    """
    excerpts = "\n\n".join(
        f"=== {data['name'].upper()} ===\n{data['merged'][:2500]}"
        for data in pkg_store.values()
    )
    system = (
        "You are a chief market analyst. Write an Executive Summary for a market research report. "
        "Produce 5-7 punchy bullet points capturing the most critical cross-cutting findings. "
        "Be specific: include named companies, USD figures, percentages, and actionable insights. "
        "Format exactly as:\n## Executive Summary\n- bullet 1\n- bullet 2\n...\n"
        "Output only the Executive Summary — nothing else."
    )
    user_msg = f"Research topic: {topic}\n\nKey findings from all research packages:\n\n{excerpts}"
    return _claude_sync(system, user_msg, max_tokens=1024)


def _assemble_report(topic: str, packages: list[dict], pkg_store: dict) -> str:
    """
    Assemble the final report by Python-concatenating all package merges.
    Eliminates the single-call stitch bottleneck that caused truncation:
    no LLM call has to produce the full report — each package is already
    a complete merged section, so we just join them in order.
    """
    exec_summary = _generate_executive_summary(topic, pkg_store)
    parts = [exec_summary]
    for pkg in packages:
        if pkg["id"] in pkg_store:
            parts.append(pkg_store[pkg["id"]]["merged"])
    return "\n\n---\n\n".join(parts)


def _run_v2(
    record: MarketResearch, db: Session, session_id: str,
    topic: str, selected: list[str], critic_llm: str,
) -> None:
    """V2 pipeline: decompose → package research loop → stitch → critic."""
    # Stage 1: Decompose (skip if resuming a previously decomposed session)
    existing_v2 = record.optimized_prompts
    if existing_v2 and existing_v2.get("version") == 2:
        packages = existing_v2["packages"]
        logger.info("run_market_research: v2 resuming — %d packages", len(packages))
    else:
        _set_status(db, record, "optimizing")
        if not record.title:
            record.title = _generate_title(topic)
            db.commit()
        packages = _decompose_packages(topic, session_id)
        record.optimized_prompts = {"version": 2, "packages": packages}
        db.commit()

    # Stage 2: Package research loop
    _set_status(db, record, "researching")

    existing_results = record.research_results or {}
    pkg_store: dict[str, dict] = (
        existing_results.get("packages", {})
        if existing_results.get("version") == 2
        else {}
    )

    carry_forward = ""
    for package in packages:
        pkg_id = package["id"]

        # Resume: skip packages already merged
        if pkg_store.get(pkg_id, {}).get("merged"):
            logger.info("run_market_research: skipping completed package %s", pkg_id)
            carry_forward = pkg_store[pkg_id]["merged"][-1500:]
            continue

        logger.info("run_market_research: package %s — %s", pkg_id, package["name"])

        pkg_prompt = _build_package_prompt(package, carry_forward)
        llm_prompts = {llm: pkg_prompt for llm in selected}

        outcome = run_parallel_research_sync(
            prompts=llm_prompts,
            system_prompt=RESEARCH_SYSTEM,
            selected_llms=selected,
            timeout=180,
            max_tokens=8192,
        )
        llm_results = outcome["results"]
        if not llm_results:
            raise RuntimeError(f"Package {pkg_id} — all LLMs failed: {outcome['errors']}")

        # Level-1 merge
        merged_pkg = _merge_package(topic, package, llm_results)

        # Completeness gate: detect and fill missing sections
        missing = _missing_sections(merged_pkg, package["sections"])
        if missing:
            logger.info("run_market_research: package %s — filling missing sections: %s", pkg_id, missing)
            continuation = _continue_truncated(topic, package, merged_pkg, missing)
            merged_pkg = merged_pkg + "\n\n" + continuation

        # Persist package result immediately (enables resumability)
        pkg_store[pkg_id] = {
            "name": package["name"],
            "scope": package["scope"],
            "sections": package["sections"],
            "merged": merged_pkg,
        }
        record.research_results = {
            "version": 2,
            "packages": pkg_store,
            "total": len(packages),
        }
        db.commit()

        carry_forward = merged_pkg[-1500:]

    # Stage 3: Sequential assembly — Python concatenation + focused exec summary
    # No single LLM call produces the full report, so output length is unbounded.
    _set_status(db, record, "merging")
    assembled = _assemble_report(topic, packages, pkg_store)
    record.merged_report = assembled
    db.commit()

    # Stage 4: Critic
    _set_status(db, record, "reflecting")
    feedback = _critic_review(topic, assembled, critic_llm)
    record.critic_feedback = feedback
    record.final_report = assembled
    db.commit()


# ── PDF generation ─────────────────────────────────────────────────────────────

def _build_pdf(record: MarketResearch, output_path: str) -> str:
    topic = record.topic
    report = record.final_report or record.merged_report or ""
    critic = record.critic_feedback or ""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _to_html(text: str) -> str:
        lines = []
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("### "):
                lines.append(f"<h3>{stripped[4:]}</h3>")
            elif stripped.startswith("## "):
                lines.append(f"<h2>{stripped[3:]}</h2>")
            elif stripped.startswith("# "):
                lines.append(f"<h1>{stripped[2:]}</h1>")
            elif stripped.startswith("- ") or stripped.startswith("* "):
                lines.append(f"<li>{stripped[2:]}</li>")
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
  li {{ margin: 0.3em 0; }}
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


# ── Main pipeline entry point ──────────────────────────────────────────────────

def run_market_research(research_id: str, db: Session) -> None:
    """
    Full market research pipeline. Called by the Celery worker.
    Updates the MarketResearch record at each stage.
    """
    record = db.get(MarketResearch, uuid.UUID(research_id))
    if not record:
        logger.error("MarketResearch %s not found", research_id)
        return

    session_id = research_id
    topic = record.topic
    selected = record.selected_llms or available_llms()
    critic_llm = record.critic_llm or "grok"

    try:
        existing_prompts = record.optimized_prompts

        # Detect v1 (rerun mode): prompts already set as {llm_id: text} with no "version" key
        if (existing_prompts is not None
                and isinstance(existing_prompts, dict)
                and "version" not in existing_prompts):
            _run_v1(record, db, session_id, topic, selected, critic_llm, existing_prompts)
        else:
            # V2: agentic work-package pipeline (new sessions + v2 reruns)
            _run_v2(record, db, session_id, topic, selected, critic_llm)

        # PDF generation (shared by both paths)
        _set_status(db, record, "generating_pdf")
        filename = f"market_research_{research_id[:8]}.pdf"
        output_path = f"/tmp/{filename}"
        pdf_path = _build_pdf(record, output_path)
        record.pdf_path = pdf_path

        # Drive upload (non-fatal)
        folder_id = os.environ.get("DRIVE_MARKET_RESEARCH_ID") or os.environ.get("GOOGLE_DRIVE_AUDIT_ROOT_ID", "")
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
            logger.info("No Drive folder configured — PDF saved locally: %s", pdf_path)
        _set_status(db, record, "pdf_ready")

        # Email delivery (optional, non-fatal)
        if record.client_email:
            _set_status(db, record, "delivering")
            display_title = record.title or topic
            download_line = (
                f'<p><a href="{record.drive_link}">Download your report (PDF)</a></p>'
                if record.drive_link else ""
            )
            try:
                send_email(
                    to=record.client_email,
                    subject=f"Market Research Ready: {display_title}",
                    body_html=(
                        f"<p>Your market research report is ready.</p>"
                        f"<p><strong>Topic:</strong> {topic}</p>"
                        f"{download_line}"
                        "<p>— Plan B AI Platform</p>"
                    ),
                )
            except Exception as email_exc:
                logger.warning("Email delivery failed (non-fatal): %s", email_exc)

        _set_status(db, record, "delivered")

    except Exception as exc:
        logger.exception("run_market_research failed for %s", research_id)
        record.status = "failed"
        record.error = str(exc)
        db.commit()
        raise
