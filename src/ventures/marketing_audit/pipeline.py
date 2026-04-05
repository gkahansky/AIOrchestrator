"""
Marketing Audit pipeline — website marketing audit delivery.

Phases:
    1 — URL Scrape           (scrape_website skill → analyze_page.py)
    2 — Competitor Scrape    (standard/premium only — included in Phase 1 result)
    3 — Audit Report         (generate_audit_report skill → Claude API)
    4 — Reports              (full PDF + Markdown; sample PDF + Markdown if report_type allows)
    5 — Human Review ★       (email notification + approval gate)
    6 — Delivery             (PDF + Markdown sent / Drive upload)

report_type field in order dict:
    "both"   (default) — full report + sample/censored report
    "full"             — full report only
    "sample"           — sample/censored report only

Order status state machine:
    pending → scraping → scraped → auditing → audited →
    generating_report → report_ready → review_pending →
    approved → delivering → delivered
              └→ revision_requested → re_delivering → delivered
              └→ failed
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic

from aiplatform.skills.media.scrape_website import scrape_website
from aiplatform.skills.media.generate_audit_report import generate_audit_report
from aiplatform.skills.storage.drive_write import drive_write
from aiplatform.skills.comms.send_email import send_email
from aiplatform.skills.finance.log_cost import log_cost
from aiplatform.skills.finance.log_revenue import log_revenue
from ventures.marketing_audit import config
from ventures.marketing_audit.sample_report import (
    generate_sample_pdf,
    generate_sample_markdown,
)


def run_order(order: dict, output_dir: str | None = None) -> dict:
    """
    Run all pipeline phases for a single audit order.
    Saves order state after each phase — safe to re-run from any checkpoint.

    Returns the updated order dict.
    """
    if output_dir is None:
        output_dir = str(Path(config.OUTPUT_DIR) / "marketing_audit")
    work_dir = Path(output_dir) / order["order_id"]
    work_dir.mkdir(parents=True, exist_ok=True)
    _save_order(order, work_dir)

    try:
        # -- Phase 1+2: Scrape target + competitors -----------------------------
        if order["status"] in ("pending", "scraping"):
            order["status"] = "scraping"
            _save_order(order, work_dir)
            scraped = _run_phase1_scrape(order, work_dir)
            order["status"] = "scraped"
            _save_json(scraped, work_dir / "scraped.json")
            _save_order(order, work_dir)
        else:
            scraped = _load_json(work_dir / "scraped.json")

        # -- Phase 3: Generate audit report via Claude --------------------------
        if order["status"] in ("scraped", "auditing"):
            order["status"] = "auditing"
            _save_order(order, work_dir)
            report_data = _run_phase3_audit(order, scraped, work_dir)
            order["status"] = "audited"
            _save_json(report_data, work_dir / "report_data.json")
            _save_order(order, work_dir)
        else:
            report_data = _load_json(work_dir / "report_data.json")

        # -- Phase 4: Generate reports ------------------------------------------
        if order["status"] in ("audited", "generating_report"):
            order["status"] = "generating_report"
            _save_order(order, work_dir)
            paths = _run_phase4_generate(order, report_data, work_dir)
            order["status"] = "report_ready"
            order["pdf_path"] = str(paths.get("pdf", ""))
            order["md_path"] = str(paths.get("md", ""))
            order["sample_pdf_path"] = str(paths.get("sample_pdf", ""))
            order["sample_md_path"] = str(paths.get("sample_md", ""))
            _save_order(order, work_dir)
        else:
            paths = {
                "pdf":        Path(order.get("pdf_path", "")),
                "md":         Path(order.get("md_path", "")),
                "sample_pdf": Path(order.get("sample_pdf_path", "")),
                "sample_md":  Path(order.get("sample_md_path", "")),
            }
        pdf_path        = paths.get("pdf", Path(""))
        md_path         = paths.get("md", Path(""))
        sample_pdf_path = paths.get("sample_pdf", Path(""))
        sample_md_path  = paths.get("sample_md", Path(""))

        # -- Phase 5: Drive upload + human review -------------------------------
        if order["status"] in ("report_ready", "review_pending"):
            # Upload to Drive first so reviewer has links before approving
            if order["status"] == "report_ready":
                _run_phase5_upload(order, pdf_path, md_path, sample_pdf_path, sample_md_path)
                _save_order(order, work_dir)

            order["status"] = "review_pending"
            _save_order(order, work_dir)
            _run_phase5_notify(order)

            if config.AUTO_APPROVE or order.get("auto_approve"):
                order["status"] = "approved"
                _save_order(order, work_dir)
            else:
                print(f"\nPipeline paused at review gate.")
                print(f"Approve via dashboard or set status to 'approved' in {work_dir / 'order.json'}.\n")
                return order

        # -- Phase 6: Delivery (email only — Drive upload already done) ---------
        if order["status"] == "approved":
            order["status"] = "delivering"
            _save_order(order, work_dir)
            _run_phase6_deliver(order)
            order["status"] = "delivered"
            order["delivered_at"] = datetime.utcnow().isoformat()
            _save_order(order, work_dir)
            # Only log revenue for paid orders — skip free samples / testing
            tier_info = config.TIERS.get(order.get("tier", "snapshot"), {})
            if order.get("client_email"):
                log_revenue(
                    venture="marketing_audit",
                    source=order.get("source", "direct"),
                    amount_usd=tier_info.get("price_usd", 0),
                    job_id=order.get("job_id"),
                    description=f"{order.get('tier','snapshot')} audit — {order.get('url','')[:80]}",
                )
            print(f"\nOK Audit {order['order_id']} delivered.")

    except Exception as exc:
        order["status"] = "failed"
        order["error"] = str(exc)
        _save_order(order, work_dir)
        raise

    return order


# --- Phase implementations ----------------------------------------------------

def _run_phase1_scrape(order: dict, work_dir: Path) -> dict:
    tier = order["tier"]
    url = order["url"]
    competitor_urls = order.get("competitor_urls", [])
    max_competitors = config.TIERS[tier]["competitors"]
    competitor_urls = competitor_urls[:max_competitors]

    print(f"  Phase 1: Scraping {url}...")
    if competitor_urls:
        print(f"    + {len(competitor_urls)} competitor(s): {', '.join(competitor_urls)}")

    result = scrape_website(url, competitor_urls=competitor_urls or None)
    print(f"    OK Scraped target + {len(result.get('competitors', []))} competitor(s)")
    return result


def _run_phase3_audit(order: dict, scraped: dict, work_dir: Path) -> dict:
    print(f"  Phase 3: Running {order['tier']} audit via Claude...")

    report_data = generate_audit_report(order, scraped)

    log_cost(
        tool_id=config.CLAUDE_MODEL,
        capability="marketing-audit",
        cost_usd=report_data.get("cost_usd", 0),
        metadata={"order_id": order["order_id"], "tier": order["tier"]},
    )

    score = report_data.get("overall_score", 0)
    grade = _score_grade(score)
    print(f"    OK Score: {score}/100 (Grade {grade}) — cost ${report_data.get('cost_usd', 0):.4f}")
    return report_data


def _run_phase4_generate(order: dict, report_data: dict, work_dir: Path) -> dict:
    """
    Generate reports based on order["report_type"]:
      "both"   (default) → full PDF + full MD + sample PDF + sample MD
      "full"             → full PDF + full MD only
      "sample"           → sample PDF + sample MD only

    Returns dict with keys: pdf, md, sample_pdf, sample_md (Path or None).
    """
    report_type = order.get("report_type", "both")
    slug = order["order_id"]
    paths: dict = {}

    want_full   = report_type in ("both", "full")
    want_sample = report_type in ("both", "sample")

    print(f"  Phase 4: Generating reports (type={report_type})...")

    if want_full:
        pdf_path = work_dir / f"{slug}-audit.pdf"
        _generate_pdf(report_data, str(pdf_path))
        print(f"    OK Full PDF:  {pdf_path.name} ({pdf_path.stat().st_size // 1024} KB)")

        md_path = work_dir / f"{slug}-audit.md"
        md_path.write_text(_build_markdown(report_data), encoding="utf-8")
        print(f"    OK Full MD:   {md_path.name}")

        paths["pdf"] = pdf_path
        paths["md"]  = md_path

    if want_sample:
        sample_pdf_path = work_dir / f"{slug}-audit-sample.pdf"
        generate_sample_pdf(report_data, str(sample_pdf_path))
        print(f"    OK Sample PDF: {sample_pdf_path.name} ({sample_pdf_path.stat().st_size // 1024} KB)")

        sample_md_path = work_dir / f"{slug}-audit-sample.md"
        sample_md_path.write_text(generate_sample_markdown(report_data), encoding="utf-8")
        print(f"    OK Sample MD:  {sample_md_path.name}")

        paths["sample_pdf"] = sample_pdf_path
        paths["sample_md"]  = sample_md_path

    return paths


def _run_phase5_upload(
    order: dict,
    pdf_path,
    md_path,
    sample_pdf_path,
    sample_md_path,
) -> None:
    """Upload reports to Drive and store view links on the order dict."""
    print(f"  Phase 5a: Uploading to Drive...")
    full_folder   = config.DRIVE_AUDIT_ROOT_ID
    sample_folder = config.DRIVE_SAMPLES_FOLDER_ID or config.DRIVE_AUDIT_ROOT_ID

    upload_targets = []
    if full_folder:
        upload_targets += [("full PDF", pdf_path, full_folder), ("full MD", md_path, full_folder)]
    if sample_folder:
        upload_targets += [("sample PDF", sample_pdf_path, sample_folder), ("sample MD", sample_md_path, sample_folder)]

    for label, path, folder_id in upload_targets:
        if path and Path(path).exists() and folder_id:
            try:
                res = drive_write(path, folder_id)
                link = res["web_view_link"]
                order[f"drive_{label.replace(' ', '_')}_link"] = link
                print(f"    OK {label} on Drive: {link}")
            except Exception as exc:
                print(f"    WARN  Drive upload failed ({label}): {exc}")


def _run_phase5_notify(order: dict) -> None:
    """Send review notification email with Drive links."""
    print(f"  Phase 5b: Review notification...")

    review_email = config.HUMAN_REVIEW_EMAIL
    if review_email:
        subject = f"[Review] Audit — {order.get('brand_name', order['url'])} ({order['tier'].title()})"
        body = _review_email_html(order)
        try:
            send_email(to=review_email, subject=subject, body_html=body)
            print(f"    OK Review email sent to {review_email}")
        except Exception as exc:
            print(f"    WARN  Review email failed: {exc}")

    print(f"\n{'-' * 60}")
    print(f"REVIEW REQUIRED — Order: {order['order_id']}")
    print(f"URL:         {order['url']}")
    print(f"Tier:        {order['tier'].upper()}")
    if order.get("drive_full_PDF_link"):
        print(f"Full PDF:    {order['drive_full_PDF_link']}")
    if order.get("drive_sample_PDF_link"):
        print(f"Sample PDF:  {order['drive_sample_PDF_link']}")
    print(f"{'-' * 60}\n")


def _run_phase6_deliver(order: dict) -> None:
    """Send delivery email to client. Drive upload already completed in Phase 5."""
    print(f"  Phase 6: Delivering to client...")

    # Paid orders use client_email; free sample orders use sample_email
    client_email = order.get("client_email") or order.get("sample_email", "")
    if not client_email:
        print(f"    No client email — skipping delivery email.")
        return

    subject = f"Your Marketing Audit — {order.get('brand_name', order['url'])}"
    body = _delivery_email_html(order)
    try:
        send_email(to=client_email, subject=subject, body_html=body)
        print(f"    OK Delivery email sent to {client_email}")
    except Exception as exc:
        print(f"    WARN  Delivery email failed: {exc}")


# --- PDF generator ------------------------------------------------------------

def _generate_pdf(report_data: dict, output_path: str) -> None:
    """
    Call generate_pdf_report.py's generate_report() function from ai-marketing-claude.
    Falls back to a plain-text PDF stub if reportlab / ai-marketing-claude is unavailable.
    """
    try:
        scripts_path = _resolve_scripts_path()
        if scripts_path not in sys.path:
            sys.path.insert(0, scripts_path)
        from generate_pdf_report import generate_report
        generate_report(report_data, output_path)
    except ImportError:
        _write_fallback_pdf(report_data, output_path)


def _resolve_scripts_path() -> str:
    # 1. Explicit env var (local dev or Railway)
    env = os.environ.get("AI_MARKETING_CLAUDE_PATH", "")
    if env:
        return str(Path(env) / "scripts")
    # 2. Git submodule: vendor/ai-marketing-claude inside this repo
    repo_root = Path(__file__).parent.parent.parent.parent
    vendor_path = repo_root / "vendor" / "ai-marketing-claude" / "scripts"
    if vendor_path.exists():
        return str(vendor_path)
    # 3. Sibling repo on local dev machines (legacy fallback)
    sibling_root = repo_root.parent
    return str(sibling_root / "ai-marketing-claude" / "scripts")


def _write_fallback_pdf(report_data: dict, output_path: str) -> None:
    """Write a minimal PDF stub if reportlab is not available."""
    try:
        from reportlab.pdfgen import canvas
        c = canvas.Canvas(output_path)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 780, f"Marketing Audit — {report_data.get('brand_name', 'Site')}")
        c.setFont("Helvetica", 12)
        c.drawString(50, 760, f"Score: {report_data.get('overall_score', '?')}/100")
        c.drawString(50, 745, f"URL: {report_data.get('url', '')}")
        c.drawString(50, 730, "Full report: see accompanying .md file")
        c.save()
    except Exception:
        Path(output_path).write_bytes(b"%PDF-1.4\n% placeholder")


# --- Markdown builder ---------------------------------------------------------

def _build_markdown(d: dict) -> str:
    score = d.get("overall_score", 0)
    grade = _score_grade(score)
    lines = [
        f"# Marketing Audit: {d.get('brand_name', d.get('url', 'Site'))}",
        f"**URL:** {d.get('url')}  ",
        f"**Date:** {d.get('date')}  ",
        f"**Business Type:** {d.get('business_type', 'Unknown')}  ",
        f"**Overall Score: {score}/100 (Grade: {grade})**",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        d.get("executive_summary", ""),
        "",
        "---",
        "",
        "## Score Breakdown",
        "",
        "| Category | Score | Weight | Key Finding |",
        "|---|---|---|---|",
    ]

    for dim, cat in d.get("categories", {}).items():
        lines.append(
            f"| {dim} | {cat.get('score', '?')}/100 | {cat.get('weight', '')} | "
            f"{cat.get('key_finding', '')} |"
        )

    # Dimension deep-dive — only when details are present
    has_details = any(cat.get("details") for cat in d.get("categories", {}).values())
    if has_details:
        lines += ["", "---", "", "## Dimension Analysis", ""]
        for dim, cat in d.get("categories", {}).items():
            details = (cat.get("details") or "").strip()
            if not details:
                continue
            lines += [
                f"### {dim} — {cat.get('score', '?')}/100",
                f"*{cat.get('key_finding', '')}*",
                "",
                details,
                "",
            ]

    lines += [
        "",
        "---",
        "",
        "## Key Findings",
        "",
    ]
    for f in d.get("findings", []):
        lines.append(f"**{f.get('severity', 'Medium')}:** {f.get('finding', '')}")
        lines.append("")

    lines += ["---", "", "## Quick Wins (This Week)", ""]
    for i, win in enumerate(d.get("quick_wins", []), 1):
        lines.append(f"{i}. {win}")

    lines += ["", "## Medium-Term Actions (1–3 Months)", ""]
    for i, action in enumerate(d.get("medium_term", []), 1):
        lines.append(f"{i}. {action}")

    lines += ["", "## Strategic Initiatives (3–6 Months)", ""]
    for i, action in enumerate(d.get("strategic", []), 1):
        lines.append(f"{i}. {action}")

    if d.get("copy_examples"):
        lines += ["", "---", "", "## Copy Examples", ""]
        for ex in d["copy_examples"]:
            lines += [
                f"**Page:** {ex.get('page')} — {ex.get('issue')}",
                f"- Before: *{ex.get('before')}*",
                f"- After: **{ex.get('after')}**",
                "",
            ]

    if d.get("competitors"):
        lines += ["---", "", "## Competitive Landscape", ""]
        header = "| | " + " | ".join(c.get("name", f"Comp {i+1}") for i, c in enumerate(d["competitors"])) + " |"
        sep = "|---|" + "---|" * len(d["competitors"])
        lines += [header, sep]
        for row in ["Positioning", "Pricing", "Social Proof", "Content"]:
            key = row.lower().replace(" ", "_")
            vals = " | ".join(c.get(key, "—") for c in d["competitors"])
            lines.append(f"| {row} | {vals} |")

    if d.get("roadmap"):
        lines += ["", "---", "", "## 30-Day Implementation Roadmap", "", d["roadmap"]]

    lines += [
        "",
        "---",
        "",
        "*Generated by EchoForge Marketing Audit — echoforge.biz*",
    ]

    return "\n".join(lines)


# --- Email templates ----------------------------------------------------------

def _review_email_html(order: dict) -> str:
    full_link   = order.get("drive_full_PDF_link", "")
    sample_link = order.get("drive_sample_PDF_link", "")
    drive_links = ""
    if full_link:
        drive_links += f'<li><a href="{full_link}">Full report (Google Drive)</a></li>'
    if sample_link:
        drive_links += f'<li><a href="{sample_link}">Sample/censored report (Google Drive)</a></li>'
    if not drive_links:
        drive_links = "<li>Drive upload failed — check worker logs</li>"

    dashboard_url = os.environ.get("RAILWAY_PUBLIC_URL", "https://planBadmin.com")
    return f"""
<p>Marketing audit report is ready for your review.</p>
<table>
  <tr><td><b>Order</b></td><td>{order['order_id']}</td></tr>
  <tr><td><b>URL</b></td><td>{order['url']}</td></tr>
  <tr><td><b>Tier</b></td><td>{order['tier'].upper()}</td></tr>
  <tr><td><b>Report type</b></td><td>{order.get('report_type', 'both')}</td></tr>
  <tr><td><b>Client</b></td><td>{order.get('client_email', 'N/A')}</td></tr>
</table>
<p><b>Reports on Google Drive:</b></p>
<ul>{drive_links}</ul>
<p><a href="{dashboard_url}">Approve or reject in the dashboard &rarr;</a></p>
"""


def _delivery_email_html(order: dict) -> str:
    tier_desc = config.TIERS[order["tier"]]["description"]
    drive_link = order.get("drive_full_PDF_link", "")
    drive_section = (
        f'<p><a href="{drive_link}" style="font-size:16px;font-weight:bold;">View your report in Google Drive &rarr;</a></p>'
        if drive_link else
        "<p>Your report is being prepared — we'll follow up shortly with the link.</p>"
    )
    return f"""
<p>Hi,</p>
<p>Your marketing audit for <b>{order.get('brand_name', order['url'])}</b> is ready.</p>
<p><b>Package:</b> {tier_desc}</p>
{drive_section}
<p>If you have questions or would like to discuss the findings, just reply to this email.</p>
<p>Thanks,<br>EchoForge Marketing Audit<br>echoforge.biz</p>
"""


# --- Helpers ------------------------------------------------------------------

def _score_grade(score: int) -> str:
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 55: return "C"
    if score >= 40: return "D"
    return "F"


def _save_order(order: dict, work_dir: Path) -> None:
    _save_json(order, work_dir / "order.json")
    try:
        from aiplatform.database.job_ops import upsert_job
        upsert_job(order, "marketing_audit")
    except Exception:
        pass  # non-blocking — JSON file is still the source of truth


def _save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _load_json(path) -> dict:
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}
