from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from aiplatform.webapp.auth import require_auth
from aiplatform.database.session import get_db
from aiplatform.database.models import AccessibilityAudit, Job
from aiplatform.webapp.schemas import AccessibilityAuditRequest
from aiplatform.webapp.worker import run_accessibility_scan_job

from aiplatform.skills.finance.log_revenue import log_revenue
from aiplatform.skills.finance.log_cost import log_cost
from pydantic import BaseModel

router = APIRouter(tags=["accessibility"])

@router.post("/initiate", status_code=status.HTTP_202_ACCEPTED)
def initiate_scan(request: AccessibilityAuditRequest, db: Session = Depends(get_db), user: str = Depends(require_auth)):
    new_audit = AccessibilityAudit(
        target_url=request.url,
        status="Queued"
    )
    db.add(new_audit)
    db.commit()
    db.refresh(new_audit)

    audit_id = str(new_audit.audit_id)

    # Create twin Job record for the master platform dashboard
    new_job = Job(
        venture="accessibility_audit",
        status="pending",
        order={"url": request.url, "audit_id": audit_id, "is_testing": request.is_testing, "is_bundled": request.is_bundled}
    )
    db.add(new_job)
    db.commit()

    # Log cost (compute/server time estimate) 
    # Log revenue if not a demo test and not already bundled into Marketing Audit's revenue
    if not request.is_testing:
        log_cost(
            tool_id="playwright-axe", 
            capability="accessibility-scan", 
            cost_usd=0.015, # Fixed compute time estimate
            metadata={"audit_id": audit_id}
        )
        if not request.is_bundled:
            log_revenue(
                venture="accessibility_audit",
                source="direct",
                amount_usd=40, # Base tier mapping if needed
                job_id=audit_id,
                description=f"Standalone WCAG audit — {request.url[:40]}"
            )
    
    task = run_accessibility_scan_job.delay(audit_id, request.url)
    
    return {"status": "Accepted", "audit_id": audit_id, "celery_task_id": str(task.id)}

@router.get("/status/{audit_id}")
def check_status(audit_id: str, db: Session = Depends(get_db)):
    audit = db.query(AccessibilityAudit).filter(AccessibilityAudit.audit_id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
        
    return {"status": audit.status, "audit_id": audit_id}

@router.get("/report/{audit_id}")
def get_report(audit_id: str, db: Session = Depends(get_db)):
    audit = db.query(AccessibilityAudit).filter(AccessibilityAudit.audit_id == audit_id).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
        
    if audit.status != "Completed":
        return {"status": audit.status, "message": "Report not ready yet"}
        
    return {
        "status": "Completed",
        "url": audit.target_url,
        "wcag_score": audit.compliance_score,
        "results": audit.raw_axe_results
    }


@router.get("/")
def list_audits(db: Session = Depends(get_db)):
    audits = db.query(AccessibilityAudit).order_by(AccessibilityAudit.created_at.desc()).limit(100).all()
    return [{
        "id": str(a.audit_id),
        "url": a.target_url,
        "status": a.status,
        "score": a.compliance_score,
        "created_at": a.created_at.isoformat()
    } for a in audits]
