from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Any, List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import json

from aiplatform.database.session import get_session
from aiplatform.database.models import AdvisoryProposal, Roadmap, RoadmapFeature
from aiplatform.webapp.auth import require_auth

router = APIRouter()

ITEM_TYPES = ["New feature", "Bug", "Feature enhancement"]
WIP_STATUSES = {"in_progress", "in_testing", "ready_for_deployment"}

class ProposalResponse(BaseModel):
    id: uuid.UUID
    advisor_id: str
    category: str
    content: Any  # JSONB in DB — can be dict or str
    status: str
    priority: int
    job_id: Optional[uuid.UUID]
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class RoadmapResponse(BaseModel):
    id: int
    title: str
    description: str
    effort_score: Optional[int]
    margin_potential: Optional[int]
    status: str
    created_at: datetime
    
    class Config:
        orm_mode = True
        from_attributes = True

@router.get("/advisors/runs")
def get_advisor_runs(limit: int = 20, user: str = Depends(require_auth)):
    """Return the most recent advisor proposals across all statuses (run history)."""
    with get_session() as db:
        rows = (
            db.query(AdvisoryProposal)
            .order_by(AdvisoryProposal.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(r.id),
                "advisor_id": r.advisor_id,
                "category": r.category,
                "content": r.content,
                "status": r.status,
                "priority": r.priority,
                "job_id": str(r.job_id) if r.job_id else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]


@router.get("/advisors/diagnostics")
def advisor_diagnostics(user: str = Depends(require_auth)):
    """Returns DB connectivity status, proposal counts, and env checks."""
    import os
    result: dict = {}

    # DB check
    try:
        with get_session() as db:
            total = db.query(AdvisoryProposal).count()
            pending = db.query(AdvisoryProposal).filter(AdvisoryProposal.status == "pending_review").count()
        result["db"] = "ok"
        result["proposal_total"] = total
        result["proposal_pending"] = pending
    except Exception as exc:
        result["db"] = f"error: {exc}"
        result["proposal_total"] = None
        result["proposal_pending"] = None

    # Env check
    result["anthropic_key_set"] = bool(os.environ.get("ANTHROPIC_API_KEY"))
    result["database_url_set"] = bool(os.environ.get("DATABASE_URL"))

    # Registry check
    try:
        registry_path = Path(__file__).parent.parent.parent.parent / "registry" / "advisors.json"
        with open(registry_path, "r") as f:
            advisors = json.load(f)
        result["registry"] = list(advisors.keys())
    except Exception as exc:
        result["registry"] = f"error: {exc}"

    # Prompt files check
    prompts_dir = Path(__file__).parent.parent.parent.parent / "registry" / "prompts"
    result["prompts"] = {p.name: p.stat().st_size for p in prompts_dir.glob("*.md")} if prompts_dir.exists() else "missing"

    return result


@router.get("/proposals")
def get_proposals(status: Optional[str] = None, advisor_id: Optional[str] = None, user: str = Depends(require_auth)):
    with get_session() as db:
        query = db.query(AdvisoryProposal)
        if status:
            query = query.filter(AdvisoryProposal.status == status)
        if advisor_id:
            query = query.filter(AdvisoryProposal.advisor_id == advisor_id)
        rows = query.order_by(AdvisoryProposal.priority.asc(), AdvisoryProposal.created_at.desc()).all()
        return [
            {
                "id": str(r.id),
                "advisor_id": r.advisor_id,
                "category": r.category,
                "content": r.content,
                "status": r.status,
                "priority": r.priority,
                "job_id": str(r.job_id) if r.job_id else None,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(proposal_id: uuid.UUID, user: str = Depends(require_auth)):
    with get_session() as db:
        proposal = db.query(AdvisoryProposal).filter(AdvisoryProposal.id == proposal_id).first()
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if proposal.status != "pending_review":
            raise HTTPException(status_code=400, detail=f"Cannot approve proposal with status {proposal.status}")

        proposal.status = "approved"
        title = f"[{proposal.advisor_id.title()}] {proposal.category}"
        content = proposal.content
        description = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else str(content)
        db.add(Roadmap(title=title[:500], description=description, item_type="New feature", status="not_started", sort_order=0))
        db.commit()
        db.refresh(proposal)
        return {
            "id": str(proposal.id), "advisor_id": proposal.advisor_id,
            "category": proposal.category, "content": proposal.content,
            "status": proposal.status, "priority": proposal.priority,
            "job_id": str(proposal.job_id) if proposal.job_id else None,
            "created_at": proposal.created_at.isoformat(),
        }

@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(proposal_id: uuid.UUID, user: str = Depends(require_auth)):
    with get_session() as db:
        proposal = db.query(AdvisoryProposal).filter(AdvisoryProposal.id == proposal_id).first()
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if proposal.status != "pending_review":
            raise HTTPException(status_code=400, detail=f"Cannot reject proposal with status {proposal.status}")
        proposal.status = "rejected"
        db.commit()
        db.refresh(proposal)
        return {
            "id": str(proposal.id), "advisor_id": proposal.advisor_id,
            "category": proposal.category, "content": proposal.content,
            "status": proposal.status, "priority": proposal.priority,
            "job_id": str(proposal.job_id) if proposal.job_id else None,
            "created_at": proposal.created_at.isoformat(),
        }

import os
import json
from pathlib import Path

_VENTURES_DIR = Path(__file__).parent.parent.parent.parent.parent / "ventures"
_venture_context_cache: str | None = None


def _load_venture_context() -> str:
    global _venture_context_cache
    if _venture_context_cache is not None:
        return _venture_context_cache
    parts: list[str] = []
    if _VENTURES_DIR.exists():
        for venture_dir in sorted(_VENTURES_DIR.iterdir()):
            claude_md = venture_dir / "CLAUDE.md"
            if claude_md.exists():
                content = claude_md.read_text(encoding="utf-8")[:3000]
                parts.append(f"### Venture: {venture_dir.name}\n{content}")
    _venture_context_cache = "\n\n".join(parts)
    return _venture_context_cache


class AdvisorPromptRequest(BaseModel):
    content: str

@router.get("/advisors")
def get_advisors(user: str = Depends(require_auth)):
    registry_path = Path(__file__).parent.parent.parent.parent / "registry" / "advisors.json"
    with open(registry_path, "r") as f:
        advisors = json.load(f)

    prompts_dir = registry_path.parent / "prompts"

    result = []
    for adv_id, data in advisors.items():
        ref = data.get("prompt_ref", adv_id + "_v1")
        prompt_file = prompts_dir / f"{ref}.md"

        content = ""
        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as pf:
                content = pf.read()

        result.append({
            "id": adv_id,
            "model": data.get("model"),
            "capabilities": data.get("capabilities", []),
            "prompt_ref": ref,
            "system_prompt": content
        })

    return result

@router.put("/advisors/{advisor_id}/prompt")
def update_advisor_prompt(advisor_id: str, prompt_data: AdvisorPromptRequest, user: str = Depends(require_auth)):
    registry_path = Path(__file__).parent.parent.parent.parent / "registry" / "advisors.json"
    with open(registry_path, "r") as f:
        advisors = json.load(f)

    if advisor_id not in advisors:
        raise HTTPException(status_code=404, detail="Advisor not found")

    ref = advisors[advisor_id].get("prompt_ref", advisor_id + "_v1")
    prompt_file = registry_path.parent / "prompts" / f"{ref}.md"

    with open(prompt_file, "w", encoding="utf-8") as pf:
        pf.write(prompt_data.content)

    return {"status": "success", "advisor_id": advisor_id}


# ── Roadmap Features ───────────────────────────────────────────────────────────

class FeatureResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


class FeatureCreate(BaseModel):
    name: str = Field(..., max_length=255)


@router.get("/roadmap/features", response_model=List[FeatureResponse])
def list_features(user: str = Depends(require_auth)):
    with get_session() as db:
        rows = db.query(RoadmapFeature).order_by(RoadmapFeature.name).all()
        return [{"id": f.id, "name": f.name, "created_at": f.created_at} for f in rows]


@router.post("/roadmap/features", response_model=FeatureResponse, status_code=201)
def create_feature(body: FeatureCreate, user: str = Depends(require_auth)):
    with get_session() as db:
        existing = db.query(RoadmapFeature).filter(RoadmapFeature.name == body.name).first()
        if existing:
            return {"id": existing.id, "name": existing.name, "created_at": existing.created_at}
        feat = RoadmapFeature(name=body.name)
        db.add(feat)
        db.commit()
        db.refresh(feat)
        return {"id": feat.id, "name": feat.name, "created_at": feat.created_at}


# ── Roadmap Items ──────────────────────────────────────────────────────────────

class RoadmapItemResponse(BaseModel):
    id: int
    title: str
    description: str
    item_type: Optional[str]
    feature_id: Optional[int]
    feature_name: Optional[str]
    status: str
    sort_order: int
    owner: Optional[str]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class RoadmapItemCreate(BaseModel):
    title: str = Field(..., max_length=100)
    description: str = Field("", max_length=500)
    item_type: str = Field("New feature")
    feature_id: Optional[int] = None
    status: str = Field("not_started")
    owner: Optional[str] = None


class RoadmapItemUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    item_type: Optional[str] = None
    feature_id: Optional[int] = None
    status: Optional[str] = None
    owner: Optional[str] = None


class ReorderRequest(BaseModel):
    ids: List[int]  # ordered list of item IDs — first = highest priority


def _item_to_dict(item: Roadmap) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description or "",
        "item_type": item.item_type,
        "feature_id": item.feature_id,
        "feature_name": item.feature.name if item.feature else None,
        "status": item.status,
        "sort_order": item.sort_order or 0,
        "owner": item.owner,
        "completed_at": item.completed_at.isoformat() if item.completed_at else None,
        "created_at": item.created_at.isoformat(),
    }


@router.get("/roadmap")
def list_roadmap_items(user: str = Depends(require_auth)):
    """Return backlog and WIP items grouped."""
    with get_session() as db:
        items = (
            db.query(Roadmap)
            .filter(Roadmap.status != "done")
            .order_by(Roadmap.sort_order.asc(), Roadmap.created_at.asc())
            .all()
        )
        backlog = [_item_to_dict(i) for i in items if i.status == "not_started"]
        wip = [_item_to_dict(i) for i in items if i.status in WIP_STATUSES]
        return {"backlog": backlog, "wip": wip}


@router.get("/roadmap/done")
def list_done_items(user: str = Depends(require_auth)):
    """Return items completed in the last 30 days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    with get_session() as db:
        items = (
            db.query(Roadmap)
            .filter(Roadmap.status == "done", Roadmap.completed_at >= cutoff)
            .order_by(Roadmap.completed_at.desc())
            .all()
        )
        return [_item_to_dict(i) for i in items]


@router.post("/roadmap", status_code=201)
def create_roadmap_item(body: RoadmapItemCreate, user: str = Depends(require_auth)):
    with get_session() as db:
        # Sort new backlog items below existing ones
        max_order = db.query(Roadmap).filter(Roadmap.status == "not_started").count()
        item = Roadmap(
            title=body.title,
            description=body.description,
            item_type=body.item_type,
            feature_id=body.feature_id,
            status="not_started",
            sort_order=max_order,
            owner=body.owner,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        if item.feature_id:
            _ = item.feature  # eager-load
        return _item_to_dict(item)


@router.put("/roadmap/{item_id}")
def update_roadmap_item(item_id: int, body: RoadmapItemUpdate, user: str = Depends(require_auth)):
    with get_session() as db:
        item = db.query(Roadmap).filter(Roadmap.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        if body.title is not None:
            item.title = body.title
        if body.description is not None:
            item.description = body.description
        if body.item_type is not None:
            item.item_type = body.item_type
        if body.feature_id is not None or "feature_id" in body.model_fields_set:
            item.feature_id = body.feature_id
        if body.status is not None:
            if body.status == "done" and item.status != "done":
                item.completed_at = datetime.now(timezone.utc)
            item.status = body.status
        if "owner" in body.model_fields_set:
            item.owner = body.owner

        db.commit()
        db.refresh(item)
        if item.feature_id:
            _ = item.feature
        return _item_to_dict(item)


@router.delete("/roadmap/{item_id}", status_code=204)
def delete_roadmap_item(item_id: int, user: str = Depends(require_auth)):
    with get_session() as db:
        item = db.query(Roadmap).filter(Roadmap.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        db.delete(item)
        db.commit()


# ── Advisor Manual Trigger ────────────────────────────────────────────────────

@router.post("/advisors/{advisor_id}/trigger")
def trigger_advisor(advisor_id: str, user: str = Depends(require_auth)):
    """Run an advisor synchronously and return the resulting proposal."""
    registry_path = Path(__file__).parent.parent.parent.parent / "registry" / "advisors.json"
    with open(registry_path, "r") as f:
        advisors = json.load(f)
    if advisor_id not in advisors:
        raise HTTPException(status_code=404, detail="Advisor not found")

    try:
        from aiplatform.skills.strategy.run_advisor import run_advisor
        result = run_advisor(advisor_id, {"event": "manual_trigger"})
        return {"status": "completed", "proposal": result}
    except Exception as exc:
        import traceback
        raise HTTPException(status_code=500, detail=f"Advisor run failed: {exc}\n{traceback.format_exc()}")


# ── Agent Chat ────────────────────────────────────────────────────────────────

class ChatMessageIn(BaseModel):
    role: str             # "user" or "assistant"
    content: str
    advisor_id: Optional[str] = None  # set for assistant messages


class ChatRequest(BaseModel):
    advisor_ids: List[str]
    messages: List[ChatMessageIn]
    session_context: Optional[str] = None  # extracted text from user-attached files


@router.post("/chat")
def chat_with_advisors(body: ChatRequest, user: str = Depends(require_auth)):
    """
    Send a conversation to one or more advisors and receive their responses.
    Each advisor gets only the user messages + its own prior replies.
    """
    import anthropic

    registry_path = Path(__file__).parent.parent.parent.parent / "registry" / "advisors.json"
    prompts_dir = registry_path.parent / "prompts"

    with open(registry_path, "r") as f:
        registry = json.load(f)

    client = anthropic.Anthropic()
    responses = []

    for advisor_id in body.advisor_ids:
        if advisor_id not in registry:
            continue

        config = registry[advisor_id]
        prompt_ref = config.get("prompt_ref", f"{advisor_id}_v1")
        prompt_file = prompts_dir / f"{prompt_ref}.md"
        system_prompt = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else (
            "You are a strategic business advisor. Provide concise, actionable insights."
        )

        venture_context = _load_venture_context()
        if venture_context:
            system_prompt = (
                system_prompt
                + "\n\n---\n## Platform Ventures Overview\n"
                + venture_context
            )

        if body.session_context:
            system_prompt = (
                system_prompt
                + "\n\n---\n## Additional Context (user-provided)\n"
                + body.session_context
            )

        # Build per-advisor message thread (user msgs + own assistant replies only)
        thread = []
        for msg in body.messages:
            if msg.role == "user":
                thread.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant" and msg.advisor_id == advisor_id:
                thread.append({"role": "assistant", "content": msg.content})

        if not thread or thread[-1]["role"] != "user":
            continue

        try:
            result = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=system_prompt,
                messages=thread,
            )
            responses.append({
                "advisor_id": advisor_id,
                "content": result.content[0].text,
            })
        except Exception as exc:
            responses.append({
                "advisor_id": advisor_id,
                "content": f"[Error: {exc}]",
            })

    return {"responses": responses}


@router.post("/context-upload")
async def upload_context_files(
    files: List[UploadFile] = File(...),
    user: str = Depends(require_auth),
) -> dict:
    """Extract text from uploaded files so the user can attach context to an agent consultation."""
    from aiplatform.skills.research.rag_store import _extract_text

    extracted_parts: list[str] = []
    filenames: list[str] = []
    for f in files:
        data = await f.read()
        fname = f.filename or "upload"
        text = _extract_text(fname, data).strip()
        if text:
            extracted_parts.append(f"--- {fname} ---\n{text}")
            filenames.append(fname)

    combined = "\n\n".join(extracted_parts)
    return {
        "extracted_text": combined,
        "filenames": filenames,
        "char_count": len(combined),
    }


@router.post("/roadmap/reorder")
def reorder_roadmap_items(body: ReorderRequest, user: str = Depends(require_auth)):
    """Update sort_order for a list of items (position in list = priority)."""
    with get_session() as db:
        for position, item_id in enumerate(body.ids):
            db.query(Roadmap).filter(Roadmap.id == item_id).update({"sort_order": position})
        db.commit()
    return {"ok": True}
