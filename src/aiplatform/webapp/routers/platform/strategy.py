from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime

from aiplatform.database.session import get_session
from aiplatform.database.models import AdvisoryProposal, Roadmap
from aiplatform.webapp.auth import require_auth

router = APIRouter()

class ProposalResponse(BaseModel):
    id: uuid.UUID
    advisor_id: str
    category: str
    content: str
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

@router.get("/proposals", response_model=List[ProposalResponse])
def get_proposals(status: Optional[str] = None, user: str = Depends(require_auth)):
    with get_session() as db:
        query = db.query(AdvisoryProposal)
        if status:
            query = query.filter(AdvisoryProposal.status == status)
        
        # Order by priority (lower is high priority) and newest first
        return query.order_by(AdvisoryProposal.priority.asc(), AdvisoryProposal.created_at.desc()).all()

@router.post("/proposals/{proposal_id}/approve", response_model=ProposalResponse)
def approve_proposal(proposal_id: uuid.UUID, user: str = Depends(require_auth)):
    with get_session() as db:
        proposal = db.query(AdvisoryProposal).filter(AdvisoryProposal.id == proposal_id).first()
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
            
        if proposal.status != "pending_review":
            raise HTTPException(status_code=400, detail=f"Cannot approve proposal with status {proposal.status}")
            
        proposal.status = "approved"
        
        # Generate a roadmap item
        # Try to extract title/description from content, or just use category
        title = f"[{proposal.advisor_id.title()}] {proposal.category}"
        
        roadmap_item = Roadmap(
            title=title,
            description=proposal.content,
            status="backlog"
        )
        db.add(roadmap_item)
        db.commit()
        db.refresh(proposal)
        
        return proposal

@router.post("/proposals/{proposal_id}/reject", response_model=ProposalResponse)
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
        
        return proposal

import os
import json
from pathlib import Path

class AdvisorPromptRequest(BaseModel):
    content: str

@router.get("/advisors")
def get_advisors(user: str = Depends(require_auth)):
    registry_path = Path(__file__).parent.parent.parent / "registry" / "advisors.json"
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
    registry_path = Path(__file__).parent.parent.parent / "registry" / "advisors.json"
    with open(registry_path, "r") as f:
        advisors = json.load(f)
        
    if advisor_id not in advisors:
        raise HTTPException(status_code=404, detail="Advisor not found")
        
    ref = advisors[advisor_id].get("prompt_ref", advisor_id + "_v1")
    prompt_file = registry_path.parent / "prompts" / f"{ref}.md"
    
    with open(prompt_file, "w", encoding="utf-8") as pf:
        pf.write(prompt_data.content)
        
    return {"status": "success", "advisor_id": advisor_id}
