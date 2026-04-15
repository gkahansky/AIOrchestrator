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
    # Must be True — Rules of Engagement acknowledgment
    tos_accepted: bool = False
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
    if not req.is_testing and not req.tos_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rules of Engagement must be accepted before submitting an order.",
        )

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

    from datetime import datetime, timezone
    input_payload = {
        "audit_id": audit_id,
        "url": req.url,
        "domain": domain,
        "tier": req.tier,
        "client_email": req.client_email or "",
        "is_testing": req.is_testing,
        "tos_accepted": req.tos_accepted,
        "tos_accepted_at": datetime.now(timezone.utc).isoformat() if req.tos_accepted else None,
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

    # Send scope verification email — best-effort, never block order creation
    try:
        _send_scope_verification_email(domain, scope_token, audit_id, client_email=req.client_email)
    except Exception:
        pass

    return SecurityAuditOrderResponse(
        audit_id=audit_id,
        job_id=str(job.id),
        scope_token=scope_token,
        scope_dns_record=f"_echoforge-verify.{domain}  TXT  \"{scope_token}\"",
        status="scope_pending",
    )


def _send_scope_verification_email(
    domain: str, scope_token: str, audit_id: str, client_email: str | None = None
) -> None:
    """
    Send a one-click scope verification email.

    Recipient selection:
      1. If client_email is provided and its domain matches the target domain → send there.
      2. Otherwise fall back to admin@/webmaster@/security@ role addresses.
    """
    import os
    from aiplatform.skills.comms.send_email import send_email

    base_url = os.environ.get("PUBLIC_API_URL", "https://api.planbadmin.com")
    verify_url = f"{base_url}/api/ventures/security-audit/verify-email?token={scope_token}"

    # Use client_email if it belongs to the target domain; otherwise use role addresses
    if client_email and client_email.split("@")[-1].lower() == domain.lower():
        to = client_email
    else:
        to = ", ".join([f"admin@{domain}", f"webmaster@{domain}", f"security@{domain}"])

    send_email(
        to=to,
        subject=f"Confirm security audit authorisation for {domain}",
        body_html=f"""<!DOCTYPE html><html><body style="font-family:sans-serif;max-width:600px;margin:40px auto;color:#1a1a2e">
<h2 style="color:#1a1a2e">Security Audit Authorisation Request</h2>
<p>Someone has requested a security audit for <strong>{domain}</strong> through EchoForge.</p>
<p>If you authorise this audit, click the button below. This confirms you own or manage this domain and consent to the scan.</p>
<p style="margin:32px 0">
  <a href="{verify_url}"
     style="background:#4361ee;color:#fff;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:bold;display:inline-block">
    Yes, I authorise this security audit
  </a>
</p>
<p style="color:#666;font-size:13px">
  If you did not request this audit and do not wish to proceed, simply ignore this email — no scan will run without your confirmation.
</p>
<p style="color:#666;font-size:13px">
  This link expires in 72 hours. Audit ID: {audit_id}
</p>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0">
<p style="color:#999;font-size:11px">EchoForge Security Audit · echoforge.biz · Questions? Reply to this email.</p>
</body></html>""",
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


# ── Email scope verification (public — no auth) ───────────────────────────────

@router.get("/verify-email")
def verify_scope_via_email(
    token: str,
    db: Session = Depends(get_db),
):
    """
    One-click email verification link — no auth required.
    Customer clicks this from their inbox to confirm domain ownership.
    On success, queues the scan automatically.
    """
    from datetime import datetime, timezone
    from fastapi.responses import HTMLResponse
    from aiplatform.webapp.worker import run_security_audit_job

    audit = db.query(SecurityAudit).filter(
        SecurityAudit.scope_token == token
    ).first()

    if not audit:
        return HTMLResponse(content=_verification_page(
            success=False,
            message="Invalid or expired verification link."
        ), status_code=404)

    if audit.scope_verified:
        return HTMLResponse(content=_verification_page(
            success=True,
            domain=audit.target_domain,
            message="This domain is already verified. Your scan is underway."
        ))

    audit.scope_verified = True
    audit.scope_verified_at = datetime.now(timezone.utc)
    audit.scope_method = "email"
    audit.status = "scope_verified"

    job = db.query(Job).filter(
        Job.venture == "security_audit",
        Job.input_data["audit_id"].astext == str(audit.audit_id),
    ).first()
    if job:
        out = dict(job.output_data or {})
        out["scope_verified"] = True
        out["status"] = "scope_verified"
        job.output_data = out
        job.status = "scope_verified"

    db.commit()

    # Queue the scan
    task = run_security_audit_job.delay(str(audit.audit_id))
    if job:
        job.celery_task_id = str(task.id)
        db.commit()

    return HTMLResponse(content=_verification_page(
        success=True,
        domain=audit.target_domain,
        message="Domain ownership confirmed. Your security audit has started — you'll receive the report by email when it's ready."
    ))


def _verification_page(success: bool, domain: str = "", message: str = "") -> str:
    icon = "✓" if success else "✗"
    color = "#22c55e" if success else "#ef4444"
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>EchoForge — Scope Verification</title>
<style>body{{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f8fafc}}
.card{{background:#fff;border-radius:16px;padding:48px;max-width:480px;text-align:center;box-shadow:0 4px 24px rgba(0,0,0,.08)}}
.icon{{font-size:64px;margin-bottom:16px}}h1{{color:#1a1a2e;margin:0 0 12px}}p{{color:#64748b;line-height:1.6}}
</style></head><body><div class="card">
<div class="icon" style="color:{color}">{icon}</div>
<h1>{'Verified' if success else 'Verification Failed'}</h1>
{"<p style='font-weight:600;color:#1a1a2e'>"+domain+"</p>" if domain else ""}
<p>{message}</p>
<p style="margin-top:24px;font-size:13px;color:#94a3b8">EchoForge Security Audit · echoforge.biz</p>
</div></body></html>"""


# ── Resend verification email ─────────────────────────────────────────────────

@router.post("/orders/{audit_id}/resend-verification-email")
def resend_verification_email(
    audit_id: str,
    _: str = Depends(require_auth),
    db: Session = Depends(get_db),
) -> dict:
    """Resend the scope verification email to role addresses at the target domain."""
    audit = db.query(SecurityAudit).filter(
        SecurityAudit.audit_id == audit_id
    ).first()
    if not audit:
        raise HTTPException(status_code=404, detail="Audit not found")
    if audit.scope_verified:
        raise HTTPException(status_code=400, detail="Scope already verified")

    job = db.query(Job).filter(
        Job.venture == "security_audit",
        Job.input_data["audit_id"].astext == audit_id,
    ).first()
    client_email = (job.input_data or {}).get("client_email") if job else None

    try:
        _send_scope_verification_email(audit.target_domain, audit.scope_token, audit_id, client_email=client_email)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {exc}")

    return {"sent": True, "domain": audit.target_domain}


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
