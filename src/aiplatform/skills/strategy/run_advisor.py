import json
import logging
from pathlib import Path
from datetime import datetime, timezone
import os

from aiplatform.database.session import SessionLocal
from aiplatform.database.models import AdvisoryProposal, ADVISOR_ID_ENUM
from aiplatform.skills.finance.log_cost import log_cost

log = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent.parent.parent / "registry" / "advisors.json"

def load_advisors_registry() -> dict:
    with open(REGISTRY_PATH, "r") as f:
        return json.load(f)

def run_advisor(advisor_id: str, context_data: dict, job_id: str = None) -> dict:
    "\""
    Run a specific advisor persona against the provided context data,
    generate a proposal, log costs, and save to DB.
    "\""
    registry = load_advisors_registry()
    if advisor_id not in registry:
        raise ValueError(f"Unknown advisor_id: {advisor_id}")
        
    config = registry[advisor_id]
    model = config.get("model", "gemini-1.5-pro")
    
    # Fake LLM Call for now since prompts are not available yet
    import uuid
    log.info(f"Running advisor {advisor_id} with model {model}")
    
    # ... LLM Logic would go here (using tool_router / google gemini API) ...
    # CRITICAL: Log cost
    log_cost(
        tool_id=model,
        capability="strategy",
        cost_usd=0.005,  # Estimated
        job_id=job_id,
        venture="platform"
    )
    
    generated_content = {
        "summary": f"Strategy suggestion from {advisor_id}",
        "raw_context": context_data
    }
    
    # Persist
    with SessionLocal() as db:
        proposal = AdvisoryProposal(
            advisor_id=advisor_id,
            category="General Advice",
            content=generated_content,
            status="pending_review",
            priority=3,
            job_id=job_id
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        
        return {
            "id": str(proposal.id),
            "advisor_id": proposal.advisor_id,
            "status": proposal.status
        }
