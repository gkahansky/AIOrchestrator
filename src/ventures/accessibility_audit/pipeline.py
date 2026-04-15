"""
Accessibility Audit venture pipeline.

Two entry points:
  run_order(audit_id, url)         — scan → generate PDF → upload → mark review_pending
  deliver_order(job_id, notes)     — send email → mark delivered
"""

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from ventures.accessibility_audit import config


# ── Phase 1: Scan + Generate + Upload ─────────────────────────────────────────

def run_order(audit_id: str, url: str) -> dict:
    """
    Execute the accessibility audit pipeline for a given order.

    Loads the AccessibilityAudit and Job records from DB, runs axe-core scan,
    generates the PDF report, uploads to Drive, and sets status to review_pending.

    Returns {"status": "review_pending", "audit_id": audit_id}.
    """
    from aiplatform.skills.audit.accessibility_scan import run_accessibility_scan
    from aiplatform.skills.audit.generate_accessibility_report import generate_accessibility_report
    from aiplatform.skills.storage.drive_organise import create_folder
    from aiplatform.skills.storage.drive_write import drive_write
    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import AccessibilityAudit, Job

    db = SessionLocal()
    audit = None
    job = None
    try:
        audit = db.query(AccessibilityAudit).filter(
            AccessibilityAudit.audit_id == audit_id
        ).first()
        job = db.query(Job).filter(
            Job.venture == "accessibility_audit",
            Job.input_data["audit_id"].astext == audit_id,
        ).first()

        if audit:
            audit.status = "Scanning"
        if job:
            job.status = "running"
            job.phase_current = 2
            current_output = dict(job.output_data or {})
            current_output["status"] = "running"
            job.output_data = current_output
        db.commit()

        # Phase 2: Run axe-core scan
        results = asyncio.run(run_accessibility_scan(url))

        # Phase 3: Generate PDF report
        tier = str((job.input_data or {}).get("tier") or "standard") if job else "standard"
        is_sample = config.TIERS.get(tier, {}).get("is_sample", False)
        work_dir = Path(config.WORK_DIR_BASE) / audit_id
        report_name = f"{audit_id}-accessibility-{'sample' if is_sample else 'report'}.pdf"
        report_meta = generate_accessibility_report(
            results, str(work_dir / report_name), tier=tier
        )

        # Phase 4: Upload to Drive
        orders_root = config.DRIVE_ACCESSIBILITY_ORDERS_ID or config.DRIVE_ACCESSIBILITY_ROOT_ID
        samples_root = config.DRIVE_ACCESSIBILITY_SAMPLES_ID or orders_root
        if not orders_root and not samples_root:
            raise RuntimeError(
                "DRIVE_ACCESSIBILITY_ORDERS_ID or DRIVE_ACCESSIBILITY_ROOT_ID must be set"
            )
        target_root = samples_root if is_sample else orders_root
        if not target_root:
            raise RuntimeError("Accessibility Drive target folder is not configured")

        folder_meta = create_folder(audit_id, target_root)
        drive_meta = drive_write(
            report_meta["pdf_path"],
            folder_meta["folder_id"],
            mime_type="application/pdf",
            filename=report_name,
            share_anyone_with_link=True,
        )

        # Phase 5: Persist results
        audit = db.query(AccessibilityAudit).filter(
            AccessibilityAudit.audit_id == audit_id
        ).first()
        job = db.query(Job).filter(
            Job.venture == "accessibility_audit",
            Job.input_data["audit_id"].astext == audit_id,
        ).first()

        if audit:
            audit.raw_axe_results = results
            audit.compliance_score = results.get("wcag_score")
            audit.status = "Review Pending"

        if job:
            current_output = dict(job.output_data or {})
            violations = results.get("violations", []) or []
            top_violations = [
                {
                    "id": v.get("id"),
                    "impact": v.get("impact"),
                    "description": v.get("description"),
                    "count": len(v.get("nodes") or []),
                    "help_url": v.get("help_url"),
                }
                for v in violations[:10]
            ]
            current_output.update({
                "audit_id": audit_id,
                "url": url,
                "wcag_score": results.get("wcag_score"),
                "tier": (job.input_data or {}).get("tier"),
                "is_sample": is_sample,
                "client_email": (job.input_data or {}).get("client_email"),
                "pdf_path": report_meta["pdf_path"],
                "pdf_size_bytes": report_meta["size_bytes"],
                "drive_report_file_id": drive_meta.get("file_id", ""),
                "drive_report_link": drive_meta.get("web_view_link", ""),
                "drive_folder_id": folder_meta.get("folder_id", ""),
                "drive_folder_link": folder_meta.get("web_view_link", ""),
                "violation_rules": report_meta["violation_rules"],
                "violation_instances": report_meta["violation_instances"],
                "top_violations": top_violations,
                "status": "review_pending",
            })
            job.status = "review_pending"
            job.phase_current = 3
            job.output_data = current_output

        db.commit()

    except Exception as exc:
        audit = db.query(AccessibilityAudit).filter(
            AccessibilityAudit.audit_id == audit_id
        ).first()
        job = db.query(Job).filter(
            Job.venture == "accessibility_audit",
            Job.input_data["audit_id"].astext == audit_id,
        ).first()
        if audit:
            audit.status = "Failed"
        if job:
            current_output = dict(job.output_data or {})
            current_output["status"] = "failed"
            current_output["error"] = str(exc)
            job.status = "failed"
            job.error_message = str(exc)
            job.output_data = current_output
        db.commit()
        raise

    finally:
        db.close()

    return {"status": "review_pending", "audit_id": str(audit_id)}


# ── Phase 6: Deliver ───────────────────────────────────────────────────────────

def deliver_order(job_id: str, review_notes: str | None = None) -> dict:
    """
    Deliver an approved accessibility audit to the client.

    Sends a delivery email with the Drive report link and marks the job delivered.

    Returns {"status": "delivered", "job_id": job_id}.
    """
    import uuid

    from aiplatform.database.session import SessionLocal
    from aiplatform.database.models import AccessibilityAudit, Job
    from aiplatform.skills.comms.send_email import send_email

    db = SessionLocal()
    try:
        parsed_job_id = uuid.UUID(job_id)
        job = db.get(Job, parsed_job_id)
        if not job:
            raise RuntimeError(f"Accessibility job not found: {job_id}")

        audit = db.query(AccessibilityAudit).filter(
            AccessibilityAudit.job_id == parsed_job_id
        ).first()

        current_output = dict(job.output_data or {})
        current_input = dict(job.input_data or {})

        if review_notes:
            current_output["review_notes"] = review_notes
            if audit:
                audit.manual_override_notes = review_notes

        client_email = (
            current_output.get("client_email")
            or current_input.get("client_email")
            or current_input.get("client_id")
        )
        report_link = current_output.get("drive_report_link", "")

        if client_email:
            if not report_link:
                raise RuntimeError("Accessibility report link missing for client delivery")

            url_display = current_input.get("url") or current_output.get("url", "your site")
            send_result = send_email(
                to=client_email,
                subject="Your accessibility audit report is ready",
                body_html=(
                    f"<!DOCTYPE html><html><body>"
                    f"<p>Your accessibility audit for <strong>{url_display}</strong> is ready.</p>"
                    f"<p><a href=\"{report_link}\">View your accessibility report</a></p>"
                    f"<p>If you have questions about the findings or remediation priorities, "
                    f"reply to this email.</p>"
                    f"</body></html>"
                ),
            )
            if send_result.get("error"):
                raise RuntimeError(f"send_email failed: {send_result['error']}")

            current_output["delivery_email_sent_to"] = client_email
            current_output["delivery_message_id"] = send_result.get("message_id", "")

        now = datetime.now(timezone.utc)
        current_output["status"] = "delivered"
        current_output["delivered_at"] = now.isoformat()
        job.status = "delivered"
        job.phase_current = 4
        job.completed_at = now
        job.error_message = None
        job.output_data = current_output

        if audit:
            audit.status = "Completed"

        db.commit()
        return {"status": "delivered", "job_id": job_id}

    except Exception as exc:
        parsed_job_id = uuid.UUID(job_id)
        job = db.get(Job, parsed_job_id)
        audit = db.query(AccessibilityAudit).filter(
            AccessibilityAudit.job_id == parsed_job_id
        ).first()
        if job:
            current_output = dict(job.output_data or {})
            current_output["status"] = "failed"
            current_output["error"] = str(exc)
            job.status = "failed"
            job.error_message = str(exc)
            job.output_data = current_output
        if audit:
            audit.status = "Failed"
        db.commit()
        raise

    finally:
        db.close()
