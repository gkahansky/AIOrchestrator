"""
Market Research pipeline — v3 Section-Based Workflow (default) + v2/v1 backwards compat.

V3 stages (section_config present):
  For each enabled section (sequential):
    1. drafting    — all LLMs research the section in parallel
    2. merging     — Level-1 merge of LLM outputs
    3. reviewing_1 — critic checks required_items + citations → PASS or REVISE
    4. (if REVISE) author fills gaps (round 2)
    5. reviewing_2 — critic reviews again → PASS or disclaimer
  Final assembly: Python concatenation of all sections + citations appendix
  generating_pdf / pdf_ready / delivering / delivered

V2 stages (optimized_prompts.version == 2):
  1. optimizing → researching (work packages) → merging → reflecting → generating_pdf

V1 (optimized_prompts is {llm_id: text}):
  researching → merging → reflecting → generating_pdf

Resumable: completed sections (or packages in v2) are skipped on retry.
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
    SECTION_LIBRARY,
    CROSS_MODULE_SYSTEM_PROMPT,
    SECTION_CRITIC_SYSTEM,
    SECTION_SUMMARY_SYSTEM,
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


# ── V3 pipeline: Section-Based Research ───────────────────────────────────────

def _build_section_research_prompt(
    section: dict,
    ref_context: str,
    system_prompt: str,
) -> str:
    """Build the per-section research prompt injected into all LLM calls."""
    ref_block = (
        f"\n\n## Already Covered in Prior Sections (do NOT repeat — reference and build on these)\n"
        f"{ref_context}"
        if ref_context else ""
    )
    return (
        f"Research topic context: see system prompt.\n\n"
        f"Section to research: {section['name']}\n\n"
        f"{section['prompt']}"
        f"{ref_block}\n\n"
        f"Cross-module instruction: {system_prompt}"
    )


def _merge_section(topic: str, section: dict, llm_results: dict[str, str]) -> str:
    outputs = "\n\n".join(
        f"=== {llm.upper()} ===\n{text}"
        for llm, text in llm_results.items()
    )
    user_msg = (
        f"Topic: {topic}\n"
        f"Section: {section['name']}\n\n"
        f"LLM outputs to synthesise:\n\n{outputs}"
    )
    return _claude_sync(PACKAGE_MERGE_SYSTEM, user_msg, max_tokens=8192)


def _critic_section(section: dict, draft: str) -> dict:
    """Run critic for one section. Returns {verdict, missing_items, uncited_claims, gaps_summary}."""
    required_list = "\n".join(f"- {item}" for item in section["required_items"])
    user_msg = (
        f"Section name: {section['name']}\n\n"
        f"Required items that must be present:\n{required_list}\n\n"
        f"Section draft to review:\n\n{draft}"
    )
    raw = _claude_sync(SECTION_CRITIC_SYSTEM, user_msg, max_tokens=512)
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start == -1 or end == 0:
        return {"verdict": "PASS", "missing_items": [], "uncited_claims": [], "gaps_summary": ""}
    try:
        return json.loads(raw[start:end])
    except json.JSONDecodeError:
        return {"verdict": "PASS", "missing_items": [], "uncited_claims": [], "gaps_summary": ""}


def _fill_section_gaps(topic: str, section: dict, draft: str, critic_result: dict) -> str:
    """Author pass: fill gaps identified by the critic."""
    gaps = critic_result.get("missing_items", [])
    uncited = critic_result.get("uncited_claims", [])
    gap_list = "\n".join(f"- {g}" for g in gaps) if gaps else ""
    uncited_list = "\n".join(f"- {c}" for c in uncited) if uncited else ""
    system = (
        "You are a market research writer improving a report section. "
        "Address the specific gaps listed. Do not rewrite the entire section — "
        "append improved or missing content using the same ## heading structure. "
        "Every new quantitative claim must include an inline citation: [Source: Name, Year]."
    )
    user_msg = (
        f"Topic: {topic}\n"
        f"Section: {section['name']}\n\n"
        f"Existing draft:\n{draft}\n\n"
        + (f"Missing required items to add:\n{gap_list}\n\n" if gap_list else "")
        + (f"Claims that need citations added:\n{uncited_list}\n\n" if uncited_list else "")
        + "Write only the additions/corrections — do not repeat content already present."
    )
    return _claude_sync(system, user_msg, max_tokens=4096)


def _build_section_summary(section_name: str, draft: str) -> str:
    """Generate a 2-sentence summary for use as reference context in subsequent sections."""
    user_msg = f"Section: {section_name}\n\nContent:\n{draft[:3000]}"
    return _claude_sync(SECTION_SUMMARY_SYSTEM, user_msg, max_tokens=128)


def _extract_citations(text: str) -> list[str]:
    """Extract all [Source: ...] citations from section text, deduplicated."""
    import re
    matches = re.findall(r'\[Source:[^\]]+\]', text)
    return list(dict.fromkeys(matches))  # preserve order, deduplicate


def _build_citations_appendix(section_results: dict) -> str:
    """Build a citations appendix grouped by section name."""
    lines = ["## Citations & Sources\n"]
    for section_id, data in section_results.items():
        citations = data.get("citations", [])
        if citations:
            lines.append(f"### {data.get('name', section_id)}")
            lines.extend(f"- {c}" for c in citations)
            lines.append("")
    return "\n".join(lines) if len(lines) > 1 else ""


_DISCLAIMER_TEMPLATE = (
    "\n\n> **Note:** Insufficient verified data was found for some required items in this section "
    "after two research rounds. The content above represents the best available information. "
    "Items not fully covered: {items}"
)


def _run_v3(
    record: MarketResearch, db: Session, session_id: str,
    topic: str, selected: list[str],
) -> None:
    """V3 pipeline: section-based research with per-section author/critic loop."""
    section_config = record.section_config
    sections = section_config.get("sections", [])
    session_system_prompt = section_config.get("system_prompt", CROSS_MODULE_SYSTEM_PROMPT)

    enabled_sections = [s for s in sections if s.get("enabled", True)]
    if not enabled_sections:
        raise RuntimeError("V3: no sections enabled in section_config")

    # Initialise or resume results store
    existing = record.research_results or {}
    section_store: dict[str, dict] = (
        existing.get("sections", {})
        if existing.get("version") == 3
        else {}
    )

    if not record.title:
        record.title = _generate_title(topic)
        db.commit()

    _set_status(db, record, "researching")

    # Build reference context from completed sections (section name → 2-sentence summary)
    ref_summaries: dict[str, str] = {
        sid: data["summary"]
        for sid, data in section_store.items()
        if data.get("summary") and data.get("status") in ("done", "disclaimer")
    }

    for section in enabled_sections:
        sec_id = section["id"]

        # Resume: skip sections already completed
        existing_sec = section_store.get(sec_id, {})
        if existing_sec.get("status") in ("done", "disclaimer"):
            logger.info("v3: skipping completed section %s", sec_id)
            if existing_sec.get("summary"):
                ref_summaries[sec_id] = existing_sec["summary"]
            continue

        logger.info("v3: starting section %s — %s", sec_id, section["name"])

        # Build reference context block
        ref_context = "\n".join(
            f"- **{name}**: {summary}"
            for name, summary in ref_summaries.items()
        )

        # Update section status to drafting
        section_store[sec_id] = {**existing_sec, "name": section["name"], "status": "drafting"}
        record.research_results = {"version": 3, "sections": section_store}
        db.commit()

        # Stage: all LLMs research section in parallel
        research_prompt = _build_section_research_prompt(section, ref_context, session_system_prompt)
        llm_prompts = {llm: research_prompt for llm in selected}

        outcome = run_parallel_research_sync(
            prompts=llm_prompts,
            system_prompt=f"You are an expert market researcher. Topic: {topic}",
            selected_llms=selected,
            timeout=180,
            max_tokens=8192,
        )
        llm_results = outcome["results"]
        if not llm_results:
            raise RuntimeError(f"Section {sec_id} — all LLMs failed: {outcome['errors']}")

        # Level-1 merge
        section_store[sec_id]["status"] = "merging"
        record.research_results = {"version": 3, "sections": section_store}
        db.commit()

        draft = _merge_section(topic, section, llm_results)

        # Critic round 1
        section_store[sec_id]["status"] = "reviewing_1"
        section_store[sec_id]["draft"] = draft
        record.research_results = {"version": 3, "sections": section_store}
        db.commit()

        critic1 = _critic_section(section, draft)
        section_store[sec_id]["critic_round_1"] = critic1

        if critic1.get("verdict") == "REVISE":
            # Author fills gaps
            addition = _fill_section_gaps(topic, section, draft, critic1)
            draft = draft + "\n\n" + addition

            # Critic round 2
            section_store[sec_id]["status"] = "reviewing_2"
            section_store[sec_id]["draft"] = draft
            record.research_results = {"version": 3, "sections": section_store}
            db.commit()

            critic2 = _critic_section(section, draft)
            section_store[sec_id]["critic_round_2"] = critic2

            if critic2.get("verdict") == "REVISE":
                # Still failing — append disclaimer
                remaining = critic2.get("missing_items", []) + critic2.get("uncited_claims", [])
                items_str = "; ".join(remaining[:5]) if remaining else "see critic feedback"
                draft += _DISCLAIMER_TEMPLATE.format(items=items_str)
                section_store[sec_id]["status"] = "disclaimer"
            else:
                section_store[sec_id]["status"] = "done"
        else:
            section_store[sec_id]["status"] = "done"

        # Build citations and summary for reference context
        citations = _extract_citations(draft)
        summary = _build_section_summary(section["name"], draft)

        section_store[sec_id]["draft"] = draft
        section_store[sec_id]["citations"] = citations
        section_store[sec_id]["summary"] = summary
        ref_summaries[sec_id] = summary

        record.research_results = {"version": 3, "sections": section_store}
        db.commit()
        logger.info("v3: section %s complete — status: %s", sec_id, section_store[sec_id]["status"])

    # Assembly: Python concatenation of all section drafts
    _set_status(db, record, "merging")

    parts = []
    for section in enabled_sections:
        sec_id = section["id"]
        draft = section_store.get(sec_id, {}).get("draft", "")
        if draft:
            parts.append(f"# {section['name']}\n\n{draft}")

    citations_appendix = _build_citations_appendix(section_store)
    if citations_appendix:
        parts.append(citations_appendix)

    assembled = "\n\n---\n\n".join(parts)
    record.merged_report = assembled
    record.final_report = assembled
    # V3 uses no separate critic pass — per-section critic feedback is stored in research_results
    record.critic_feedback = json.dumps({
        sec_id: {
            "round_1": data.get("critic_round_1"),
            "round_2": data.get("critic_round_2"),
            "status": data.get("status"),
        }
        for sec_id, data in section_store.items()
    }, indent=2)
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
        record.started_at = datetime.now(timezone.utc)
        db.commit()

        existing_prompts = record.optimized_prompts

        if record.section_config:
            # V3: section-based pipeline (new sessions with section_config set)
            _run_v3(record, db, session_id, topic, selected)
        elif (existing_prompts is not None
                and isinstance(existing_prompts, dict)
                and "version" not in existing_prompts):
            # V1 (rerun mode): prompts already set as {llm_id: text} with no "version" key
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

        record.completed_at = datetime.now(timezone.utc)
        _set_status(db, record, "delivered")

    except Exception as exc:
        logger.exception("run_market_research failed for %s", research_id)
        record.status = "failed"
        record.error = str(exc)
        record.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise
