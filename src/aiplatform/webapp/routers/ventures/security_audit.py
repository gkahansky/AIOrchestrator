"""
Security Audit venture router.

Endpoints:
  POST /orders                        — create new audit order
  GET  /orders                        — list all audit orders
  GET  /orders/{audit_id}             — get order detail
  POST /orders/{audit_id}/verify-scope — attempt DNS TXT scope verification
  POST /orders/{audit_id}/review      — approve / reject (human review gate)
  POST /orders/{audit_id}/deliver     — trigger client delivery
"""

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from aiplatform.database.models import Job, SecurityAudit
from aiplatform.database.session import get_db
from aiplatform.webapp.auth import require_auth
from aiplatform.skills.security.scope_validator import extract_domain, generate_scope_token

router = APIRouter()


# ── Request / Response schemas ─────────────────────────────────────────────────

class SecurityAuditOrderRequest(BaseModel):
    url: str
    tier: str = "starter"               # starter | professional | agency
    client_email: str | None = None
    is_testing: bool = False
    # Optional context for authenticated testing (professional tier+)
    auth_username: str | None = None
    auth_password: str | None = None
    auth_login_url: str | None = None

class SecurityAuditOrderResponse(BaseModel):
    audit_id: str
    job_id: str
    scope_token: str
    scope_dns_record: str
    status: str

class ScopeVerifyResponse(BaseModel):
    audit_id: str
    verified: bool
    method: str | None
    reason: str | None

class ReviewRequest(BaseModel):
    action: str                          # "approve" | "reject"
    notes: str | None = None

class DeliverRequest(BaseModel):
    notes: str | None = None


# ── Create order ──────────────────────────────────────────────────────────────

@router.post("/orders", response_model=SecurityAuditOrderResponse,
             status_code=status.HTTP_202_ACCEPTED)
def create_security_audit_order(
    req: SecurityAuditOrderRequest,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> SecurityAuditOrderResponse:
    """
    Submit a new security audit order.

    The order starts in 'scope_pending' status. The caller must complete
    scope verification (DNS TXT method) before the scan will be queued.
    """
    domain = extract_domain(req.url)
    scope_token = generate_scope_token()
    audit_id = str(uuid.uuid4())

    # Create SecurityAudit record
    audit = SecurityAudit(
        audit_id=audit_id,
        target_url=req.url,
        target_domain=domain,
        tier=req.tier,
        scope_token=scope_token,
        scope_verified=False,
        status="scope_pending",
        auth_username=req.auth_username,
        auth_password=req.auth_password,  # TODO: encrypt before storing
        auth_login_url=req.auth_login_url,
    )
    db.add(audit)
    db.flush()

    input_payload = {
        "audit_id": audit_id,
        "url": req.url,
        "domain": domain,
        "tier": req.tier,
        "client_email": req.client_email or "",
        "is_testing": req.is_testing,
        "scope_token": scope_token,
        "status": "scope_pending",
    }

    job = Job(
        venture="security_audit",
        status="scope_pending",
        phase_current=1,
        phase_total=6,
        input_data=input_payload,
        output_data=dict(input_payload),
        environment="staging" if req.is_testing else "production",
    )
    db.add(job)
    db.flush()

    audit.job_id = job.id
    db.commit()
    db.refresh(job)

    return SecurityAuditOrderResponse(
        audit_id=audit_id,
        job_id=str(job.id),
        scope_token=scope_token,
        scope_dns_record=f"_echoforge-verify.{domain}  TXT  \"{scope_token}\"",
        status="scope_pending",
    )


# ── List orders ───────────────────────────────────────────────────────────────

@router.get("/orders")
def list_security_audit_orders(
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> list[dict]:
    audits = (
        db.query(SecurityAudit)
        .order_by(SecurityAudit.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "audit_id": str(a.audit_id),
            "job_id": str(a.job_id) if a.job_id else None,
            "target_url": a.target_url,
            "target_domain": a.target_domain,
            "tier": a.tier,
            "status": a.status,
            "scope_verified": a.scope_verified,
            "risk_score": a.risk_score,
            "findings_count": len(a.findings_json or []),
            "created_at": a.created_at.isoformat(),
        }
        for a in audits
    ]


# ── Get order detail ──────────────────────────────────────────────────────────

@router.get("/orders/{audit_id}")
def get_security_audit_order(
    audit_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    audit = db.query(SecurityAudit).filter(
        SecurityAudit.audit_id == audit_id
    ).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    job = db.query(Job).filter(Job.id == audit.job_id).first() if audit.job_id else None

    return {
        "audit_id": str(audit.audit_id),
        "job_id": str(audit.job_id) if audit.job_id else None,
        "target_url": audit.target_url,
        "target_domain": audit.target_domain,
        "tier": audit.tier,
        "status": audit.status,
        "scope_token": audit.scope_token,
        "scope_dns_record": (
            f"_echoforge-verify.{audit.target_domain}  TXT  \"{audit.scope_token}\""
        ),
        "scope_verified": audit.scope_verified,
        "scope_verified_at": audit.scope_verified_at.isoformat() if audit.scope_verified_at else None,
        "risk_score": audit.risk_score,
        "risk_rating": (job.output_data or {}).get("risk_rating", "") if job else "",
        "findings_count": len(audit.findings_json or []),
        "findings": audit.findings_json or [],
        "attack_chains": audit.attack_chains or [],
        "output_data": dict(job.output_data or {}) if job else {},
        "created_at": audit.created_at.isoformat(),
    }


# ── Scope verification ────────────────────────────────────────────────────────

@router.post("/orders/{audit_id}/verify-scope", response_model=ScopeVerifyResponse)
def verify_scope(
    audit_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> ScopeVerifyResponse:
    """
    Attempt DNS TXT record scope verification.
    Returns the result — call again after the customer has set their DNS record.
    If verified, the order is automatically queued for scanning.
    """
    from ventures.security_audit.pipeline import verify_scope as pipeline_verify_scope

    audit = db.query(SecurityAudit).filter(
        SecurityAudit.audit_id == audit_id
    ).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    if audit.scope_verified:
        return ScopeVerifyResponse(
            audit_id=audit_id,
            verified=True,
            method=audit.scope_method,
            reason="Already verified",
        )

    result = pipeline_verify_scope(audit_id)

    if result["verified"]:
        # Queue the scan
        from aiplatform.webapp.worker import run_security_audit_job
        task = run_security_audit_job.delay(audit_id)
        # Update job with celery task ID
        job = db.query(Job).filter(
            Job.venture == "security_audit",
            Job.input_data["audit_id"].astext == audit_id,
        ).first()
        if job:
            job.celery_task_id = str(task.id)
            db.commit()

    return ScopeVerifyResponse(
        audit_id=audit_id,
        verified=result.get("verified", False),
        method=result.get("method"),
        reason=result.get("reason"),
    )


# ── Manual scope approval (for testing / manual override) ─────────────────────

@router.post("/orders/{audit_id}/approve-scope")
def approve_scope_manually(
    audit_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    """
    Manually mark scope as verified and queue the scan.
    Use this for testing or when a client has provided a signed authorisation letter.
    """
    from datetime import datetime, timezone
    from aiplatform.webapp.worker import run_security_audit_job

    audit = db.query(SecurityAudit).filter(
        SecurityAudit.audit_id == audit_id
    ).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    audit.scope_verified = True
    audit.scope_verified_at = datetime.now(timezone.utc)
    audit.scope_method = "manual"
    audit.status = "scope_verified"

    job = db.query(Job).filter(
        Job.venture == "security_audit",
        Job.input_data["audit_id"].astext == audit_id,
    ).first()
    if job:
        out = dict(job.output_data or {})
        out["scope_verified"] = True
        out["status"] = "scope_verified"
        job.output_data = out
        job.status = "scope_verified"

    db.commit()

    task = run_security_audit_job.delay(audit_id)
    if job:
        job.celery_task_id = str(task.id)
        db.commit()

    return {"status": "scope_verified", "queued": True, "celery_task_id": str(task.id)}


# ── Human review gate ──────────────────────────────────────────────────────────

@router.post("/orders/{audit_id}/review")
def review_security_audit(
    audit_id: str,
    req: ReviewRequest,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    if req.action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

    audit = db.query(SecurityAudit).filter(
        SecurityAudit.audit_id == audit_id
    ).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    job = db.query(Job).filter(Job.id == audit.job_id).first() if audit.job_id else None

    new_status = "approved" if req.action == "approve" else "rejected"
    audit.status = new_status
    if req.notes:
        audit.reviewer_notes = req.notes

    if job:
        out = dict(job.output_data or {})
        out["status"] = new_status
        if req.notes:
            out["reviewer_notes"] = req.notes
        job.status = new_status
        job.output_data = out

    db.commit()
    return {"status": new_status, "audit_id": audit_id}


# ── Delivery ──────────────────────────────────────────────────────────────────

@router.post("/orders/{audit_id}/deliver")
def deliver_security_audit(
    audit_id: str,
    req: DeliverRequest,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    """Trigger client delivery for an approved audit."""
    audit = db.query(SecurityAudit).filter(
        SecurityAudit.audit_id == audit_id
    ).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")

    job = db.query(Job).filter(Job.id == audit.job_id).first() if audit.job_id else None
    if not job:
        raise HTTPException(status_code=404, detail="Job record not found")

    if audit.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Audit is in status '{audit.status}' — must be 'approved' before delivery"
        )

    from aiplatform.webapp.worker import deliver_security_audit_job
    task = deliver_security_audit_job.delay(str(job.id), req.notes)
    return {"status": "delivering", "celery_task_id": str(task.id)}
