from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uuid
from datetime import datetime

from aiplatform.database.session import get_session
from aiplatform.database.models import AdvisoryProposal, Roadmap
from aiplatform.webapp.routers.platform.auth import get_current_user

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
def get_proposals(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    with get_session() as db:
        query = db.query(AdvisoryProposal)
        if status:
            query = query.filter(AdvisoryProposal.status == status)
        
        # Order by priority (lower is high priority) and newest first
        return query.order_by(AdvisoryProposal.priority.asc(), AdvisoryProposal.created_at.desc()).all()

@router.post("/proposals/{proposal_id}/approve", response_model=ProposalResponse)
def approve_proposal(proposal_id: uuid.UUID, user: dict = Depends(get_current_user)):
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
def reject_proposal(proposal_id: uuid.UUID, user: dict = Depends(get_current_user)):
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
