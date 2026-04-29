"""
Market Research venture router.

  POST /api/ventures/market-research/sessions                       — create + queue a research session
  POST /api/ventures/market-research/sessions/{id}/upload           — upload RAG documents
  GET  /api/ventures/market-research/sessions                       — list sessions
  GET  /api/ventures/market-research/sessions/{id}                  — get session detail
  GET  /api/ventures/market-research/sessions/{id}/sections/{sec}   — get single section detail (V3)
  GET  /api/ventures/market-research/available-llms                 — which LLMs are configured
  GET  /api/ventures/market-research/section-library                — default section library
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aiplatform.database.models import MarketResearch
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.skills.research.multi_llm_research import available_llms
from aiplatform.skills.research.rag_store import ingest_document

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class SectionConfigEntry(BaseModel):
    id: str
    name: str
    enabled: bool = True
    prompt: str
    locked: bool = False
    required_items: list[str] = []
    expected_outputs: list[str] = []


class SectionConfig(BaseModel):
    version: int = 3
    system_prompt: str | None = None   # None → use default CROSS_MODULE_SYSTEM_PROMPT
    sections: list[SectionConfigEntry]


class CreateResearchRequest(BaseModel):
    topic: str
    selected_llms: list[str] | None = None   # None → all available
    critic_llm: str = "grok"
    client_email: str | None = None
    section_config: SectionConfig | None = None  # None → V2 pipeline (backwards compat)


class ResearchSummary(BaseModel):
    id: str
    topic: str
    title: str | None
    status: str
    selected_llms: list[str]
    critic_llm: str
    drive_link: str | None
    created_at: str


class ResearchDetail(ResearchSummary):
    section_config: dict | None
    optimized_prompts: dict | None
    research_results: dict | None
    merged_report: str | None
    critic_feedback: str | None
    final_report: str | None
    error: str | None


def _to_summary(r: MarketResearch) -> ResearchSummary:
    return ResearchSummary(
        id=str(r.id),
        topic=r.topic,
        title=r.title,
        status=r.status,
        selected_llms=r.selected_llms or [],
        critic_llm=r.critic_llm,
        drive_link=r.drive_link,
        created_at=r.created_at.isoformat(),
    )


def _to_detail(r: MarketResearch) -> ResearchDetail:
    return ResearchDetail(
        id=str(r.id),
        topic=r.topic,
        title=r.title,
        status=r.status,
        selected_llms=r.selected_llms or [],
        critic_llm=r.critic_llm,
        drive_link=r.drive_link,
        created_at=r.created_at.isoformat(),
        section_config=r.section_config,
        optimized_prompts=r.optimized_prompts,
        research_results=r.research_results,
        merged_report=r.merged_report,
        critic_feedback=r.critic_feedback,
        final_report=r.final_report,
        error=r.error,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/available-llms")
def get_available_llms(_: str = Depends(require_auth)) -> dict:
    """Return which LLMs are configured (API key present)."""
    return {"available": available_llms()}


@router.post("/sessions", status_code=status.HTTP_202_ACCEPTED)
def create_session(
    req: CreateResearchRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> ResearchSummary:
    """Create a market research session and queue the pipeline."""
    from aiplatform.worker import run_market_research as celery_task

    avail = available_llms()
    selected = req.selected_llms or avail
    invalid = [llm for llm in selected if llm not in avail]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"LLMs not configured (missing API keys): {invalid}",
        )

    # Build section_config for V3 — apply default system prompt if not provided
    sc = None
    if req.section_config is not None:
        from ventures.market_research.config import CROSS_MODULE_SYSTEM_PROMPT
        sc = req.section_config.model_dump()
        if not sc.get("system_prompt"):
            sc["system_prompt"] = CROSS_MODULE_SYSTEM_PROMPT

    record = MarketResearch(
        topic=req.topic,
        selected_llms=selected,
        critic_llm=req.critic_llm,
        client_email=req.client_email,
        section_config=sc,
        status="pending",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    task = celery_task.delay(str(record.id))
    record.celery_task_id = task.id
    db.commit()

    return _to_summary(record)


@router.post("/sessions/{session_id}/upload", status_code=status.HTTP_200_OK)
async def upload_documents(
    session_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """Upload RAG documents for a research session."""
    try:
        record_id = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    record = db.get(MarketResearch, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    point_ids: list[str] = list(record.rag_doc_ids or [])
    filenames: list[str] = list(record.uploaded_filenames or [])
    ingested = []
    for f in files:
        data = await f.read()
        ids = ingest_document(f.filename or "upload", data, session_id)
        point_ids.extend(ids)
        fname = f.filename or "upload"
        if fname not in filenames:
            filenames.append(fname)
        ingested.append({"filename": fname, "chunks": len(ids)})

    record.rag_doc_ids = point_ids
    record.uploaded_filenames = filenames
    db.commit()

    return {"ingested": ingested, "total_chunks": len(point_ids)}


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> list[ResearchSummary]:
    records = db.query(MarketResearch).order_by(MarketResearch.created_at.desc()).limit(50).all()
    return [_to_summary(r) for r in records]


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> ResearchDetail:
    try:
        record_id = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    record = db.get(MarketResearch, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    return _to_detail(record)


class HistorySectionEntry(BaseModel):
    id: str
    name: str
    enabled: bool
    prompt: str


class ResearchHistory(BaseModel):
    session_id: str
    topic: str
    title: str | None
    status: str
    selected_llms: list[str]
    system_prompt: str | None
    sections: list[HistorySectionEntry]
    uploaded_files: list[str]
    started_at: str | None
    completed_at: str | None
    duration_s: float | None
    error: str | None
    drive_link: str | None
    created_at: str


@router.get("/sessions/{session_id}/history")
def get_session_history(
    session_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> ResearchHistory:
    """Return a structured history/audit snapshot for a research session."""
    try:
        record_id = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    record = db.get(MarketResearch, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    sc = record.section_config or {}
    system_prompt = sc.get("system_prompt") if sc else None
    raw_sections = sc.get("sections", []) if sc else []
    sections = [
        HistorySectionEntry(
            id=s.get("id", ""),
            name=s.get("name", ""),
            enabled=s.get("enabled", True),
            prompt=s.get("prompt", ""),
        )
        for s in raw_sections
    ]

    duration_s: float | None = None
    if record.started_at and record.completed_at:
        duration_s = (record.completed_at - record.started_at).total_seconds()

    return ResearchHistory(
        session_id=str(record.id),
        topic=record.topic,
        title=record.title,
        status=record.status,
        selected_llms=record.selected_llms or [],
        system_prompt=system_prompt,
        sections=sections,
        uploaded_files=record.uploaded_filenames or [],
        started_at=record.started_at.isoformat() if record.started_at else None,
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
        duration_s=duration_s,
        error=record.error,
        drive_link=record.drive_link,
        created_at=record.created_at.isoformat(),
    )


@router.get("/section-library")
def get_section_library(_: str = Depends(require_auth)) -> dict:
    """Return the default V3 section library so the frontend can populate the section selector."""
    from ventures.market_research.config import SECTION_LIBRARY, CROSS_MODULE_SYSTEM_PROMPT
    return {
        "sections": SECTION_LIBRARY,
        "default_system_prompt": CROSS_MODULE_SYSTEM_PROMPT,
    }


@router.get("/sessions/{session_id}/sections/{section_id}")
def get_section_detail(
    session_id: str,
    section_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> dict:
    """Return the full detail for a single V3 section (draft, critic rounds, citations, status)."""
    try:
        record_id = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    record = db.get(MarketResearch, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")

    if not record.section_config:
        raise HTTPException(status_code=400, detail="Session is not a V3 section-based session")

    results = record.research_results or {}
    sections = results.get("sections", {})
    section_data = sections.get(section_id)
    if section_data is None:
        raise HTTPException(status_code=404, detail=f"Section '{section_id}' not found or not yet started")

    # Find section config entry for name/required_items
    sc_sections = (record.section_config or {}).get("sections", [])
    sc_entry = next((s for s in sc_sections if s["id"] == section_id), {})

    return {
        "section_id": section_id,
        "name": section_data.get("name", sc_entry.get("name", section_id)),
        "status": section_data.get("status", "pending"),
        "draft": section_data.get("draft", ""),
        "citations": section_data.get("citations", []),
        "summary": section_data.get("summary", ""),
        "critic_round_1": section_data.get("critic_round_1"),
        "critic_round_2": section_data.get("critic_round_2"),
        "required_items": sc_entry.get("required_items", []),
        "expected_outputs": sc_entry.get("expected_outputs", []),
    }


class RerunRequest(BaseModel):
    adjusted_prompts: dict[str, str]            # {llm_id: edited_prompt}
    selected_llms: list[str] | None = None      # defaults to original session's selection
    critic_llm: str | None = None


@router.post("/sessions/{session_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_session(
    session_id: str,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> ResearchSummary:
    """Re-queue a failed or stuck-pending session without cloning it."""
    from aiplatform.worker import run_market_research as celery_task

    try:
        record_id = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    record = db.get(MarketResearch, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Session not found")
    _RETRYABLE = {"failed", "pending", "optimizing", "researching", "merging", "reflecting", "generating_pdf"}
    if record.status not in _RETRYABLE:
        raise HTTPException(status_code=400, detail=f"Session cannot be retried in status: {record.status}")

    record.status = "pending"
    record.error = None
    db.commit()

    task = celery_task.delay(str(record.id))
    record.celery_task_id = task.id
    db.commit()
    db.refresh(record)
    return _to_summary(record)


@router.post("/sessions/{session_id}/rerun", status_code=status.HTTP_202_ACCEPTED)
def rerun_session(
    session_id: str,
    req: RerunRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
) -> ResearchSummary:
    """Clone a completed session with adjusted prompts and queue a new pipeline run."""
    from aiplatform.worker import run_market_research as celery_task

    try:
        record_id = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID")

    original = db.get(MarketResearch, record_id)
    if not original:
        raise HTTPException(status_code=404, detail="Session not found")

    new_record = MarketResearch(
        topic=original.topic,
        selected_llms=req.selected_llms or original.selected_llms,
        critic_llm=req.critic_llm or original.critic_llm,
        client_email=original.client_email,
        # Inject the adjusted prompts so the pipeline skips the optimizer step
        optimized_prompts=req.adjusted_prompts,
        status="researching",   # skip optimizing — prompts already set
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    task = celery_task.delay(str(new_record.id))
    new_record.celery_task_id = task.id
    db.commit()

    return _to_summary(new_record)
