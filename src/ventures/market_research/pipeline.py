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

import base64
import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from aiplatform.database.models import MarketResearch
from aiplatform.skills.research.multi_llm_research import (
    run_parallel_research_sync,
    available_llms,
)
from aiplatform.skills.research.rag_store import retrieve_context
from aiplatform.skills.research.web_search import google_search
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
    EXEC_SUMMARY_SYSTEM,
)
from ventures.market_research.registry import build_report_directives, DEPTH_MAX_TOKENS

import anthropic
import asyncio

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _set_status(db: Session, record: MarketResearch, status: str) -> None:
    record.status = status
    record.updated_at = datetime.now(timezone.utc)
    db.commit()


def _fetch_web_context(topic: str, section_name: str, num_results: int = 5) -> str:
    """
    Run two targeted SerpAPI queries for this topic+section and return formatted
    results for injection into the LLM prompt as grounding context.
    Returns empty string if SERPAPI_KEY is not configured or all queries fail.
    """
    if not os.environ.get("SERPAPI_KEY"):
        logger.info("web search skipped — SERPAPI_KEY not set")
        return ""

    year = datetime.now(timezone.utc).year
    queries = [
        f"{topic} {section_name} {year}",
        f"{topic} {section_name} statistics data {year}",
    ]

    seen_urls: set[str] = set()
    snippets: list[str] = []

    for query in queries:
        try:
            results = google_search(query, num_results=num_results)
            for r in results.get("organic_results", []):
                url = r.get("link", "")
                title = r.get("title", "").strip()
                snippet = r.get("snippet", "").strip()
                if not snippet or url in seen_urls:
                    continue
                seen_urls.add(url)
                snippets.append(f"**{title}**\n{url}\n> {snippet}")
        except Exception as exc:
            logger.warning("web search failed for query '%s': %s", query, exc)

    if not snippets:
        return ""

    return (
        "## Live Web Research — Retrieved Now\n"
        "The following sources were fetched via live web search. "
        "Cite these directly using [Source: Publication Name, Year] format and "
        "prioritise them over any training-data knowledge.\n\n"
        + "\n\n".join(snippets)
    )


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


def _build_package_prompt(package: dict, carry_forward: str = "", web_context: str = "") -> str:
    sections_list = "\n".join(f"- {s}" for s in package["sections"])
    web_block = f"\n\n{web_context}" if web_context else ""
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
        f"- Minimum 300 words per section"
        f"{web_block}"
        f"{carry}"
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

        web_context = _fetch_web_context(topic, package["name"])
        pkg_prompt = _build_package_prompt(package, carry_forward, web_context)
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
    report_config: dict | None = None,
    web_context: str = "",
) -> str:
    """Build the per-section research prompt injected into all LLM calls."""
    web_block = f"\n\n{web_context}" if web_context else ""
    ref_block = (
        f"\n\n## Already Covered in Prior Sections (do NOT repeat — reference and build on these)\n"
        f"{ref_context}"
        if ref_context else ""
    )
    directives_block = build_report_directives(report_config) if report_config else ""
    return (
        f"Research topic context: see system prompt.\n\n"
        f"Section to research: {section['name']}\n\n"
        f"{section['prompt']}"
        f"{web_block}"
        f"{ref_block}\n\n"
        f"Cross-module instruction: {system_prompt}"
        f"{directives_block}"
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
    raw = _claude_sync(SECTION_CRITIC_SYSTEM, user_msg, max_tokens=1024)
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


def _compose_executive_summary(
    topic: str,
    sections_takeaways: list[tuple[str, list[str]]],
    exec_prompt: str,
) -> str:
    """Compose the executive summary from per-section key takeaways collected by the critic."""
    takeaways_block = ""
    for section_name, takeaways in sections_takeaways:
        if takeaways:
            items = "\n".join(f"  - {t}" for t in takeaways)
            takeaways_block += f"\n### {section_name}\n{items}\n"

    user_msg = (
        f"Topic: {topic}\n\n"
        f"Key takeaways from each research section:\n{takeaways_block}\n\n"
        f"Instructions:\n{exec_prompt}"
    )
    return _claude_sync(EXEC_SUMMARY_SYSTEM, user_msg, max_tokens=4096)


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

    # report_config drives output depth (token budget) and writing style/framework directives
    report_config: dict | None = record.report_config
    section_max_tokens = DEPTH_MAX_TOKENS.get(
        (report_config or {}).get("output_depth", "standard"), 8192
    )

    enabled_sections = [s for s in sections if s.get("enabled", True)]
    if not enabled_sections:
        raise RuntimeError("V3: no sections enabled in section_config")

    # Separate the executive summary section — it is composed post-loop from takeaways
    exec_summary_section = next(
        (s for s in enabled_sections if s["id"] == "executive_summary"), None
    )
    research_sections = [s for s in enabled_sections if s["id"] != "executive_summary"]

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

    for section in research_sections:
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

        # Fetch live web search results to ground LLMs with current data
        web_context = _fetch_web_context(topic, section["name"])

        # Stage: all LLMs research section in parallel
        research_prompt = _build_section_research_prompt(
            section, ref_context, session_system_prompt, report_config, web_context
        )
        llm_prompts = {llm: research_prompt for llm in selected}

        outcome = run_parallel_research_sync(
            prompts=llm_prompts,
            system_prompt=f"You are an expert market researcher. Topic: {topic}",
            selected_llms=selected,
            timeout=180,
            max_tokens=section_max_tokens,
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
        key_takeaways = critic1.get("key_takeaways", [])  # default: use round-1 takeaways

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
            key_takeaways = critic2.get("key_takeaways", [])  # override with round-2 takeaways

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

        section_store[sec_id]["key_takeaways"] = key_takeaways

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

    # Compose executive summary from per-section key takeaways (runs after all sections)
    if exec_summary_section:
        existing_exec = section_store.get("executive_summary", {})
        if existing_exec.get("status") not in ("done", "disclaimer"):
            logger.info("v3: composing executive summary from section takeaways")
            sections_takeaways = [
                (s["name"], section_store.get(s["id"], {}).get("key_takeaways", []))
                for s in research_sections
            ]
            exec_prompt = (
                exec_summary_section.get("prompt")
                or exec_summary_section.get("default_prompt", "")
            )
            exec_draft = _compose_executive_summary(topic, sections_takeaways, exec_prompt)
            section_store["executive_summary"] = {
                "name": exec_summary_section["name"],
                "status": "done",
                "draft": exec_draft,
                "citations": [],
                "summary": "",
                "key_takeaways": [],
            }
            record.research_results = {"version": 3, "sections": section_store}
            db.commit()
            logger.info("v3: executive summary complete")

    # Assembly: Python concatenation of all section drafts
    _set_status(db, record, "merging")

    citations_appendix = _build_citations_appendix(section_store)

    # Table of contents — built from sections that have content
    toc_entries: list[str] = []
    n = 1
    for section in enabled_sections:
        if section_store.get(section["id"], {}).get("draft"):
            toc_entries.append(f"{n}. {section['name']}")
            n += 1
    if citations_appendix:
        toc_entries.append(f"{n}. Citations & Sources")
    toc_block = "# Table of Contents\n\n" + "\n".join(toc_entries)

    parts = [toc_block]
    for section in enabled_sections:
        sec_id = section["id"]
        draft = section_store.get(sec_id, {}).get("draft", "")
        if draft:
            parts.append(f"# {section['name']}\n\n{draft}")

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
    import base64
    import tempfile

    from aiplatform.skills.media.capture_visual import generate_chart, screenshot_url
    from aiplatform.skills.media.render_markdown import extract_visual_markers, markdown_to_html

    topic  = record.topic
    report = record.final_report or record.merged_report or ""
    critic = record.critic_feedback or ""
    now    = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ── Resolve visual markers embedded in the report ─────────────────────────
    # Claude places [SCREENSHOT: url | caption] or [GENERATE IMAGE: desc | caption]
    # markers in the text.  We capture each and convert to a base64 data URI so
    # Playwright can embed them directly in the PDF without external network calls.
    visuals: dict[str, str] = {}   # {full_marker_text: "data:image/png;base64,..."}
    markers = extract_visual_markers(report)

    if markers:
        with tempfile.TemporaryDirectory() as vis_tmp:
            for marker_text, marker_type, content, caption in markers:
                img_path = os.path.join(vis_tmp, f"vis_{len(visuals)}.png")
                if marker_type == "SCREENSHOT":
                    result = screenshot_url(content.strip(), img_path)
                    if not result.get("success"):
                        # Screenshot failed (auth-gated, bot-blocked, or unreachable).
                        # Fall back to a Gemini-generated UI mockup using the caption
                        # and URL as context so the visual slot is never left empty.
                        logger.info(
                            "Screenshot failed for %s (%s) — falling back to generated UI mockup",
                            content[:80], result.get("error", "unknown"),
                        )
                        fallback_desc = (
                            f"{caption}. "
                            f"This is a representation of the page at: {content.strip()}."
                        )
                        result = generate_chart(fallback_desc, img_path, mode="ui")
                else:  # GENERATE IMAGE
                    result = generate_chart(content.strip(), img_path)

                if result.get("success") and Path(img_path).exists():
                    b64 = base64.b64encode(Path(img_path).read_bytes()).decode()
                    visuals[marker_text] = f"data:image/png;base64,{b64}"
                else:
                    logger.warning(
                        "Visual capture failed for %s marker (including fallback) — %s: %s",
                        marker_type, content[:80], result.get("error", "unknown"),
                    )

    # ── Convert markdown to HTML ───────────────────────────────────────────────
    body_html   = markdown_to_html(report, visuals=visuals)
    critic_html = markdown_to_html(critic) if critic else ""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  /* ── Base typography ────────────────────────────────────────────────────── */
  body {{
    font-family: Georgia, serif;
    margin: 0;
    color: #1a1a1a;
    line-height: 1.75;
    font-size: 11pt;
  }}
  h1 {{
    color: #0f172a;
    border-bottom: 3px solid #3b82f6;
    padding-bottom: 10px;
    margin-top: 0;
    font-size: 1.9em;
  }}
  h2 {{
    color: #1e3a5f;
    margin-top: 2em;
    margin-bottom: 0.4em;
    font-size: 1.35em;
    border-bottom: 1px solid #dbeafe;
    padding-bottom: 4px;
  }}
  h3 {{ color: #374151; margin-top: 1.4em; font-size: 1.1em; }}
  h4 {{ color: #4b5563; margin-top: 1.2em; font-size: 1em; font-style: italic; }}
  p  {{ margin: 0.55em 0; }}
  ul, ol {{ margin: 0.4em 0 0.4em 1.4em; padding: 0; }}
  li {{ margin: 0.3em 0; }}
  blockquote {{
    margin: 1em 0;
    padding: 8px 16px;
    border-left: 4px solid #93c5fd;
    background: #eff6ff;
    color: #1e3a5f;
    font-style: italic;
  }}
  code {{
    background: #f1f5f9;
    border-radius: 3px;
    padding: 1px 4px;
    font-family: monospace;
    font-size: 0.88em;
  }}
  hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 1.5em 0; }}
  sup.citation {{
    font-size: 0.72em;
    color: #6b7280;
    vertical-align: super;
  }}

  /* ── Tables ─────────────────────────────────────────────────────────────── */
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 1.4em 0;
    font-size: 0.91em;
    break-inside: avoid;
  }}
  thead tr {{
    background: #1e3a5f;
    color: #ffffff;
  }}
  thead th {{
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    font-family: Helvetica, Arial, sans-serif;
    letter-spacing: 0.02em;
    font-size: 0.92em;
  }}
  tbody tr:nth-child(even)  {{ background: #f8fafc; }}
  tbody tr:nth-child(odd)   {{ background: #ffffff; }}
  tbody td {{
    padding: 9px 14px;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
  }}

  /* ── Figures (screenshots + generated charts) ────────────────────────────── */
  figure {{
    margin: 1.8em 0;
    text-align: center;
    break-inside: avoid;
  }}
  figure img {{
    max-width: 100%;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.10);
  }}
  figcaption {{
    margin-top: 8px;
    color: #6b7280;
    font-size: 0.85em;
    font-style: italic;
  }}

  /* ── Page chrome ─────────────────────────────────────────────────────────── */
  .meta {{
    color: #6b7280;
    font-size: 0.9em;
    margin-bottom: 28px;
    font-family: Helvetica, Arial, sans-serif;
  }}
  .critic-section {{
    background: #f0fdf4;
    border-left: 4px solid #22c55e;
    padding: 14px 18px;
    margin: 28px 0;
    border-radius: 4px;
    font-size: 0.92em;
  }}
  .critic-section h3 {{ margin: 0 0 8px; color: #15803d; }}
  footer {{
    margin-top: 52px;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;
    color: #9ca3af;
    font-size: 0.82em;
    text-align: center;
    font-family: Helvetica, Arial, sans-serif;
  }}
</style>
</head>
<body>
<h1>Market Research for {topic}</h1>
<div class="meta">
  Generated: {now}
</div>
{body_html}
{{"<div class='critic-section'><h3>Critic Review</h3>" + critic_html + "</div>" if critic_html else ""}}
<footer>Confidential &mdash; Generated by Plan B AI Platform</footer>
</body>
</html>"""

    from playwright.sync_api import sync_playwright

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(out),
            print_background=True,
            format="A4",
            margin={"top": "0.65in", "bottom": "0.65in", "left": "0.55in", "right": "0.55in"},
        )
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
            display_title = (record.title or topic).replace("\n", " ").replace("\r", " ").strip()
            prompt_flat = topic.replace("\n", " ").replace("\r", " ").strip()
            prompt_preview = (prompt_flat[:160].rsplit(" ", 1)[0] + "…") if len(prompt_flat) > 160 else prompt_flat
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
                        f"<p><strong>{display_title}</strong></p>"
                        f"<p>Prompt: {prompt_preview}</p>"
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
