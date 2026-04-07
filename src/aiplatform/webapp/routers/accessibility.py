from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from aiplatform.webapp.auth import require_auth
from aiplatform.database.session import get_db
from aiplatform.database.models import AccessibilityAudit
from aiplatform.webapp.schemas import AccessibilityAuditRequest
from aiplatform.webapp.worker import run_accessibility_scan_job

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

