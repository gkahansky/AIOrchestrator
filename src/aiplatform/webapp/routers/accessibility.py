from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from aiplatform.webapp.auth import require_auth
from aiplatform.database.session import get_db
from aiplatform.database.models import AccessibilityAudit, Job
from aiplatform.webapp.schemas import AccessibilityAuditRequest
from aiplatform.webapp.worker import run_accessibility_scan_job

from aiplatform.skills.finance.log_revenue import log_revenue
from aiplatform.skills.finance.log_cost import log_cost

router = APIRouter(tags=["accessibility"])

@router.post("/initiate", status_code=status.HTTP_202_ACCEPTED)
def initiate_scan(request: AccessibilityAuditRequest, db: Session = Depends(get_db), user: str = Depends(require_auth)):
    new_audit = AccessibilityAudit(
        target_url=request.url,
        status="Queued"
    )
    db.add(new_audit)
    db.flush()

    audit_id = str(new_audit.audit_id)
    client_email = request.client_email or request.client_id
    job_payload = {
        "order_id": audit_id,
        "audit_id": audit_id,
        "url": request.url,
        "tier": request.tier,
        "client_id": request.client_id,
        "client_email": client_email,
        "is_testing": request.is_testing,
        "is_bundled": request.is_bundled,
        "status": "pending",
    }

    # Create twin Job record for the master platform dashboard
    new_job = Job(
        venture="accessibility_audit",
        status="pending",
        phase_current=1,
        phase_total=4,
        input_data=job_payload,
        output_data=dict(job_payload),
    )
    db.add(new_job)
    db.flush()
    new_audit.job_id = new_job.id
    db.commit()
    db.refresh(new_job)
    job_id = str(new_job.id)

    # CRM ingestion (H-11): record the paying customer (skips when testing/empty).
    from aiplatform.database.crm_ops import ingest_customer
    if not request.is_testing:
        ingest_customer(client_email or None, "accessibility_audit")

    # Log cost (compute/server time estimate) 
    # Log revenue if not a demo test and not already bundled into Marketing Audit's revenue
    if not request.is_testing:
        log_cost(
            tool_id="playwright-axe", 
            capability="accessibility-scan", 
            cost_usd=0.015, # Fixed compute time estimate
            metadata={"audit_id": audit_id},
            job_id=job_id,
            venture="accessibility_audit",
        )
        if not request.is_bundled:
            log_revenue(
                venture="accessibility_audit",
                source="direct",
                amount_usd=40, # Base tier mapping if needed
                job_id=job_id,
                description=f"Standalone WCAG audit — {request.url[:40]}"
            )
    
    task = run_accessibility_scan_job.delay(audit_id, request.url)
    new_job.celery_task_id = str(task.id)
    db.commit()
    
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
    job = db.query(Job).filter(Job.id == audit.job_id).first() if audit.job_id else None
        
    if audit.status != "Completed":
        return {"status": audit.status, "message": "Report not ready yet"}
        
    return {
        "status": "Completed",
        "url": audit.target_url,
        "wcag_score": audit.compliance_score,
        "results": audit.raw_axe_results,
        "drive_report_link": (job.output_data or {}).get("drive_report_link", "") if job else "",
    }


@router.get("/")
def list_audits(db: Session = Depends(get_db)):
    audits = db.query(AccessibilityAudit).order_by(AccessibilityAudit.created_at.desc()).limit(100).all()
    return [{
        "id": str(a.audit_id),
        "job_id": str(a.job_id) if a.job_id else None,
        "url": a.target_url,
        "status": a.status,
        "score": a.compliance_score,
        "created_at": a.created_at.isoformat()
    } for a in audits]
