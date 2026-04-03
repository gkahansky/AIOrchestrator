"""
Etsy pipeline — orchestrates the 7-phase flow by chaining platform skills.
Architecture rule: imports from aiplatform/skills/ only — never the reverse.

Phases:
  1  — Idea & Theme Generation    ✓ Sprint 2
  2  — Subject List Generation    ✓ Sprint 2
  3  — Image Generation           ✓ Sprint 3
  4  — Packaging                  ✓ Sprint 3
  5  — Human Review ★             ✓ Sprint 4
  6  — Store Upload ★             ✓ Sprint 4
  7  — Promotion                  Sprint 5
"""

import csv
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

import anthropic

from aiplatform.skills.research.web_search import google_trends, google_search
from aiplatform.skills.research.competitor_scan import scan_etsy_listings, scan_etsy_prices
from aiplatform.skills.research.trend_analysis import score_theme, rank_themes
from aiplatform.skills.storage.drive_write import drive_write
from aiplatform.skills.storage.drive_organise import create_folder, list_folder
from aiplatform.skills.media.generate_image import generate_image
from aiplatform.skills.media.resize_image import resize_to_variants
from aiplatform.skills.media.create_mockup import create_mockup
from aiplatform.skills.packaging.create_zip import create_zip
from aiplatform.skills.packaging.generate_pdf import generate_pdf
from aiplatform.skills.comms.send_email import send_email
from aiplatform.skills.comms.send_slack import send_slack
from aiplatform.skills.marketplace.etsy_upload import (
    create_draft_listing,
    upload_listing_image,
    upload_listing_file,
    get_listing,
    get_shop_listings,
)
from ventures.etsy import config


# Seed themes to evaluate — broad enough to surface unexpected winners
SEED_THEMES = [
    "botanical line art",
    "minimalist flower print",
    "celestial moon and stars",
    "boho sun illustration",
    "abstract watercolour",
    "vintage botanical illustration",
    "geometric animal art",
    "zen meditation print",
    "tropical leaf art",
    "wildflower meadow print",
    "mountain landscape line art",
    "mushroom cottagecore print",
    "mid century modern abstract",
    "Japandi minimalist art",
    "retro groovy print",
    "cat line art illustration",
    "ocean wave art print",
    "fern botanical print",
    "dragonfly illustration",
    "hummingbird watercolour",
    "koi fish art print",
    "fox forest illustration",
    "butterfly botanical print",
    "succulent cactus art",
    "lavender field print",
]


# ─── Phase 1: Theme Research ──────────────────────────────────────────────────

def run_phase_1(
    seed_themes: list[str] = None,
    run_date: str = None,
    save_to_drive: bool = True,
    output_dir: str = "./output/research",
) -> dict:
    """
    Research and score all seed themes. Save results to local dir + Drive /01-research/.

    Returns:
        {
            run_date       (str),
            total_themes   (int),
            passing_themes (int),   # score >= 60
            themes         (list),  # all scored themes, sorted by score
            csv_path       (str),
            json_path      (str),
            drive_csv_id   (str | None),
            drive_json_id  (str | None),
        }
    """
    themes = seed_themes or SEED_THEMES
    run_date = run_date or date.today().isoformat()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Phase 1: researching {len(themes)} themes...")
    scored = []

    for i, theme in enumerate(themes, 1):
        print(f"  [{i}/{len(themes)}] {theme}")
        try:
            theme_data = _research_theme(theme)
            scored.append(score_theme(theme_data))
        except Exception as e:
            print(f"    WARNING: skipping '{theme}' — {e}")
        # Be gentle on SerpAPI rate limits
        if i < len(themes):
            time.sleep(1.5)

    ranked = rank_themes(scored)
    passing = [t for t in ranked if t["proceed"]]

    # Save CSV
    csv_path = output_dir / f"themes-{run_date}.csv"
    _save_themes_csv(ranked, csv_path)

    # Save JSON
    json_path = output_dir / f"themes-{run_date}.json"
    json_path.write_text(json.dumps({"run_date": run_date, "themes": ranked}, indent=2))

    result = {
        "run_date":       run_date,
        "total_themes":   len(ranked),
        "passing_themes": len(passing),
        "themes":         ranked,
        "csv_path":       str(csv_path),
        "json_path":      str(json_path),
        "drive_csv_id":   None,
        "drive_json_id":  None,
    }

    if save_to_drive and config.DRIVE_01_RESEARCH:
        print("  Uploading to Drive /01-research/...")
        result["drive_csv_id"]  = drive_write(csv_path,  config.DRIVE_01_RESEARCH)["file_id"]
        result["drive_json_id"] = drive_write(json_path, config.DRIVE_01_RESEARCH)["file_id"]

    return result


def _research_theme(theme: str) -> dict:
    """Gather demand, competition, and price data for a single theme."""
    # Demand: Google Trends for "[theme] print" over 90 days
    trends = google_trends(f"{theme} print", period="today 3-m")

    # Competition + price: Etsy listing count and prices
    etsy   = scan_etsy_listings(f"{theme} wall art", num_results=10)
    prices = scan_etsy_prices(f"{theme} digital print etsy")

    avg_price = prices["avg_price_usd"] or etsy["avg_price_usd"] or 4.99

    return {
        "theme":          theme,
        "avg_interest":   trends["avg_interest"],
        "peak_interest":  trends["peak_interest"],
        "listing_count":  etsy["listing_count"],
        "avg_price_usd":  avg_price,
    }


def _save_themes_csv(themes: list[dict], path: Path) -> None:
    fields = ["theme", "slug", "score", "demand", "competition", "monetisation",
              "proceed", "listing_count", "avg_price_usd", "avg_interest"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(themes)


# ─── Phase 2: Subject Generation ─────────────────────────────────────────────

def run_phase_2(
    theme: str,
    theme_slug: str = None,
    save_to_drive: bool = True,
    output_dir: str = "./output/subjects",
) -> dict:
    """
    Use Claude to generate 20 image subjects for a theme.
    Save subjects.json to local dir + Drive /02-subjects/{theme-slug}/.

    Returns:
        {
            theme         (str),
            theme_slug    (str),
            subjects      (list),  # 20 subject dicts
            json_path     (str),
            drive_file_id (str | None),
        }
    """
    import re
    theme_slug = theme_slug or re.sub(r'[^a-z0-9]+', '-', theme.lower()).strip('-')
    output_dir = Path(output_dir) / theme_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Phase 2: generating 20 subjects for '{theme}'...")
    subjects = _generate_subjects_with_claude(theme)

    json_path = output_dir / f"subjects-{theme_slug}.json"
    json_path.write_text(json.dumps(subjects, indent=2))
    print(f"  Saved {len(subjects)} subjects -> {json_path}")

    result = {
        "theme":         theme,
        "theme_slug":    theme_slug,
        "subjects":      subjects,
        "json_path":     str(json_path),
        "drive_file_id": None,
    }

    if save_to_drive and config.DRIVE_02_SUBJECTS:
        print("  Uploading to Drive /02-subjects/...")
        # Create per-theme subfolder in Drive
        folder = create_folder(theme_slug, config.DRIVE_02_SUBJECTS)
        result["drive_file_id"] = drive_write(json_path, folder["folder_id"])["file_id"]

    return result


def _generate_subjects_with_claude(theme: str) -> list[dict]:
    """Ask Claude to generate 20 subjects for an Etsy theme."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    system = (
        "You are an expert Etsy shop assistant specialising in digital printable wall art and SEO. "
        "You generate structured product data for listings. "
        "Output only valid JSON — no markdown, no explanation, no code fences."
    )

    prompt = f"""Generate 20 unique image subjects for the Etsy wall art theme: "{theme}".

Each subject must be a JSON object with exactly these fields:
- subject_id: lowercase hyphenated slug, e.g. "{theme.split()[0].lower()}-01"
- title_draft: SEO-optimised Etsy listing title, max 140 chars, lead with primary keyword
- description: Full Etsy listing description, max 2000 chars. No section labels or headings.
    Write it as three blocks of plain text separated by a blank line:
    Block 1 (2-3 sentences): Describe the artwork — what it depicts, artistic style, mood,
    colour palette, and what makes it special. Weave in SEO keywords naturally.
    Block 2 (copy this exactly, replacing only the em-dashes with hyphens):
    "WHAT YOU GET:\n- 8 print-ready files in 4 sizes, each as PNG + JPG:\n  Square 3000 x 3000 px (1:1) | Portrait 2400 x 3600 px (2:3) | Landscape 3600 x 2400 px (3:2) | Widescreen 3840 x 2160 px (16:9)\n- Instant digital download - no waiting, no shipping\n- Print at home or at any local or online print shop\n- High resolution - crisp and sharp at all standard frame sizes"
    Block 3 (1-2 sentences): Who it is perfect for (gift ideas, room types, interior styles).
    End with a gentle call to action.
- image_prompt: detailed DALL-E 3 image generation prompt (no aspect ratio flags)
- style_notes: one sentence of art direction (style, colour palette, mood)
- etsy_tags: array of exactly 13 Etsy SEO tags (max 20 chars each, Etsy requirement)
- price_usd: 4.99 for standard quality, 7.99 for premium quality
- quality_tier: "standard" or "premium"
- status: "pending"

Return a JSON array of 20 objects. No other text."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        system=system,
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if present
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                raw = part
                break

    raw = raw.strip()

    # Find the JSON array boundaries cleanly
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError("Claude response did not contain a JSON array.")
    raw = raw[start:end]

    subjects = json.loads(raw)

    # Ensure status field is set correctly
    for s in subjects:
        s["status"] = "pending"

    return subjects


# ─── Phase 3: Image Generation ───────────────────────────────────────────────

def run_phase_3(
    subject: dict,
    save_to_drive: bool = True,
    output_dir: str = "./output/images",
) -> dict:
    """
    Generate the raw image, resize to 4 variants, and create 3 mockups.

    Args:
        subject:       Subject dict from Phase 2 (must have subject_id, image_prompt,
                       title_draft, style_notes, quality_tier).
        save_to_drive: Upload results to Drive /03-images/{slug}/.
        output_dir:    Local root for image outputs.

    Returns:
        {
            subject_id   (str),
            slug         (str),
            raw_image    (str),       # path to DALL-E 3 PNG
            variants     (dict),      # resize_to_variants result
            mockups      (dict),      # create_mockup result
            drive_folder_id (str | None),
            total_cost   (float),
        }
    """
    slug       = subject.get("subject_id", "listing")
    prompt     = subject.get("image_prompt", "")
    tier       = subject.get("quality_tier", "standard")
    style      = subject.get("style_notes", "")
    title      = subject.get("title_draft", slug)

    base_dir   = Path(output_dir) / slug
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"Phase 3 [{slug}]: generating image...")
    img_result = generate_image(
        prompt=prompt,
        aspect_ratio="1:1",
        quality_tier=tier,
        output_dir=base_dir,
        filename=f"{slug}-raw",
    )
    raw_path   = img_result["image_path"]
    total_cost = img_result.get("cost", 0.0)
    print(f"  Raw image: {raw_path}  (cost ${total_cost:.4f})")

    print(f"  Resizing to 4 variants...")
    variants = resize_to_variants(
        source_path=raw_path,
        output_dir=base_dir / "variants",
    )

    print(f"  Creating 3 mockups...")
    mockups = create_mockup(
        artwork_path=raw_path,
        artwork_description=f"{title}. {style}",
        output_dir=base_dir / "mockups",
        slug=slug,
    )
    total_cost += mockups.get("cost", 0.0)
    print(f"  Mockup cost: ${mockups.get('cost', 0):.4f}  |  Total: ${total_cost:.4f}")

    # Save metadata.json alongside the images — single source of truth for this listing
    metadata = {
        "subject_id":      slug,
        "title":           subject.get("title_draft", ""),
        "description":     subject.get("description", ""),
        "etsy_tags":       subject.get("etsy_tags", subject.get("target_keywords", [])),
        "price_usd":       subject.get("price_usd", config.DEFAULT_PRICE_USD),
        "quality_tier":    subject.get("quality_tier", "standard"),
        "style_notes":     subject.get("style_notes", ""),
        "image_prompt":    subject.get("image_prompt", ""),
        "revised_prompt":  img_result.get("prompt", ""),
        "tool_used":       img_result.get("tool_used", ""),
        "total_cost_usd":  round(total_cost, 4),
        "status":          "generated",
        "raw_image":       raw_path,
        "variants":        variants,
        "mockups":         {k: v for k, v in mockups.items() if k != "cost"},
    }
    metadata_path = base_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))
    print(f"  Metadata  : {metadata_path}")

    result = {
        "subject_id":      slug,
        "slug":            slug,
        "raw_image":       raw_path,
        "variants":        variants,
        "mockups":         mockups,
        "metadata_path":   str(metadata_path),
        "drive_folder_id": None,
        "total_cost":      total_cost,
    }

    if save_to_drive and config.DRIVE_03_IMAGES:
        print("  Uploading to Drive /03-images/...")
        folder = create_folder(slug, config.DRIVE_03_IMAGES)
        fid    = folder["folder_id"]
        drive_write(raw_path, fid)
        for v in variants.values():
            if isinstance(v, dict):
                for fmt in ("png", "jpg"):
                    if fmt in v:
                        drive_write(v[fmt], fid)
        for mp in (mockups.get("product_shot"), mockups.get("living_room"), mockups.get("flat_lay")):
            if mp and Path(mp).exists():
                drive_write(mp, fid)
        drive_write(str(metadata_path), fid)
        result["drive_folder_id"] = fid

    return result


# ─── Phase 4: Packaging ───────────────────────────────────────────────────────

def run_phase_4(
    subject: dict,
    phase3_result: dict,
    save_to_drive: bool = True,
    output_dir: str = "./output/packages",
) -> dict:
    """
    Create delivery ZIP and review-sheet PDF.

    Args:
        subject:        Subject dict from Phase 2.
        phase3_result:  Result dict from run_phase_3().
        save_to_drive:  Upload ZIP + PDF to Drive /04-packages/{slug}/.
        output_dir:     Local root for package outputs.

    Returns:
        {
            subject_id    (str),
            slug          (str),
            zip_path      (str),
            zip_size_bytes (int),
            zip_within_limit (bool),
            pdf_path      (str),
            checks_passed (dict),
            drive_zip_id  (str | None),
            drive_pdf_id  (str | None),
        }
    """
    slug     = phase3_result.get("slug", subject.get("subject_id", "listing"))
    base_dir = Path(output_dir) / slug
    base_dir.mkdir(parents=True, exist_ok=True)

    print(f"Phase 4 [{slug}]: creating delivery ZIP...")
    zip_path = base_dir / f"{slug}-delivery.zip"
    zip_result = create_zip(
        variants=phase3_result["variants"],
        output_path=str(zip_path),
    )
    print(f"  ZIP: {zip_result['size_bytes'] / (1024*1024):.2f} MB  "
          f"({'OK' if zip_result['within_limit'] else 'OVER LIMIT'})")

    # Build mockup_paths list
    mockups = phase3_result.get("mockups", {})
    mockup_paths = [
        p for k, p in mockups.items()
        if k in ("product_shot", "living_room", "flat_lay") and p and Path(p).exists()
    ]

    print(f"  Generating review PDF...")
    pdf_path = base_dir / f"{slug}-review.pdf"
    listing_data = {
        "slug":               slug,
        "title":              subject.get("title_draft", ""),
        "description":        subject.get("description", ""),
        "tags":               subject.get("etsy_tags", subject.get("target_keywords", [])),
        "price_usd":          subject.get("price_usd", config.DEFAULT_PRICE_USD),
        "mockup_paths":       mockup_paths,
        "raw_image_path":     phase3_result.get("raw_image", ""),
        "zip_path":           zip_result["zip_path"],
        "zip_size_bytes":     zip_result["size_bytes"],
        "metadata_drive_link": "",
        "zip_drive_link":     "",
    }
    pdf_result = generate_pdf(listing_data, str(pdf_path))
    print(f"  PDF: {pdf_result['pdf_path']}")

    result = {
        "subject_id":        slug,
        "slug":              slug,
        "zip_path":          zip_result["zip_path"],
        "zip_size_bytes":    zip_result["size_bytes"],
        "zip_within_limit":  zip_result["within_limit"],
        "pdf_path":          pdf_result["pdf_path"],
        "checks_passed":     pdf_result["checks_passed"],
        "drive_zip_id":      None,
        "drive_pdf_id":      None,
    }

    if save_to_drive and config.DRIVE_04_PACKAGES:
        print("  Uploading to Drive /04-packages/...")
        folder = create_folder(slug, config.DRIVE_04_PACKAGES)
        fid    = folder["folder_id"]
        result["drive_zip_id"] = drive_write(zip_result["zip_path"], fid)["file_id"]
        result["drive_pdf_id"] = drive_write(pdf_result["pdf_path"],  fid)["file_id"]

    return result


# ─── Phase 5: Human Review Gate ──────────────────────────────────────────────

def run_phase_5_notify(
    pending_subjects: list[dict],
    review_email: str | None = None,
) -> dict:
    """
    Send human review notification for a batch of packaged subjects.
    Moves review PDFs to Drive /05-review/pending/ and sends email + Slack alert.

    Args:
        pending_subjects: List of phase4 result dicts (each has slug, pdf_path,
                          zip_path, drive_pdf_id, drive_zip_id).
        review_email:     Override HUMAN_REVIEW_EMAIL env var.

    Returns:
        {
            notified:    int,        # subjects notified
            email_sent:  bool,
            slack_sent:  bool,
            drive_ids:   dict,       # slug -> drive_pending_id
        }
    """
    to_email = review_email or os.environ.get("HUMAN_REVIEW_EMAIL", os.environ.get("GMAIL_ADDRESS", ""))
    drive_ids: dict[str, str] = {}

    slugs = [s.get("slug", s.get("subject_id", "?")) for s in pending_subjects]
    n = len(pending_subjects)

    print(f"Phase 5: notifying review for {n} listing(s): {', '.join(slugs)}")

    # Move review PDFs to Drive /05-review/pending/ and collect Drive links
    drive_links: list[str] = []
    for subject in pending_subjects:
        slug     = subject.get("slug", subject.get("subject_id", "listing"))
        pdf_path = subject.get("pdf_path", "")

        if config.DRIVE_05_REVIEW_PENDING and pdf_path and Path(pdf_path).exists():
            result = drive_write(pdf_path, config.DRIVE_05_REVIEW_PENDING)
            fid = result.get("file_id", "")
            drive_ids[slug] = fid
            link = f"https://drive.google.com/file/d/{fid}/view" if fid else "(Drive upload failed)"
            drive_links.append(f"• {slug}: {link}")
            print(f"  Uploaded review PDF for {slug} -> Drive /05-review/pending/")
        else:
            drive_links.append(f"• {slug}: (review PDF not uploaded)")

    # Build email body
    drive_list_html = "\n".join(f"<li>{l.lstrip('• ')}</li>" for l in drive_links)
    email_body = f"""
<h2>Etsy Review Batch Ready — {n} listing(s) pending your approval</h2>
<p>The following listings have been generated and packaged. Please review each PDF
and move the listing to <strong>/05-review/approved/</strong> or <strong>/05-review/rejected/</strong>.</p>
<h3>Review PDFs:</h3>
<ul>{drive_list_html}</ul>
<h3>Actions:</h3>
<ul>
  <li><strong>Approve</strong> — move listing folder to /05-review/approved/</li>
  <li><strong>Reject</strong> — move to /05-review/rejected/ (will be skipped this cycle)</li>
</ul>
<p>The pipeline will check for approval decisions every {config.REVIEW_POLL_INTERVAL_MIN} minutes.</p>
"""

    email_ok = False
    if to_email:
        result = send_email(
            to=to_email,
            subject=f"[Etsy] {n} listing(s) ready for review",
            body_html=email_body,
        )
        email_ok = "error" not in result
        if email_ok:
            print(f"  [OK] Email sent to {to_email}")
        else:
            print(f"  [FAIL] Email failed: {result.get('error')}")
    else:
        print("  [!] No review email address set (HUMAN_REVIEW_EMAIL)")

    # Slack notification
    slack_text = f"🖼 *Etsy review batch ready* — {n} listing(s) pending approval\n" + \
                 "\n".join(drive_links)
    slack_result = send_slack(text=slack_text)
    slack_ok = "error" not in slack_result
    if slack_ok:
        print(f"  [OK] Slack notification sent")
    else:
        # Slack is optional — non-fatal
        print(f"  [!] Slack not sent: {slack_result.get('error')}")

    return {
        "notified":   n,
        "slugs":      slugs,
        "email_sent": email_ok,
        "slack_sent": slack_ok,
        "drive_ids":  drive_ids,
    }


def poll_for_approvals(
    slugs: list[str],
    timeout_minutes: int = 720,  # 12 hours max wait
) -> dict:
    """
    Poll Drive /05-review/approved/ and /05-review/rejected/ until all slugs are resolved.
    Returns {approved: [...], rejected: [...]} when all decisions are in or timeout reached.

    In practice, run this in a background scheduler. For CLI use, it blocks.
    """
    from aiplatform.skills.storage.drive_organise import list_folder as drive_list

    pending  = set(slugs)
    approved = []
    rejected = []
    start    = datetime.now(timezone.utc)
    interval = config.REVIEW_POLL_INTERVAL_MIN * 60

    while pending:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() / 60
        if elapsed > timeout_minutes:
            print(f"  [!] poll_for_approvals timed out after {timeout_minutes} min. Remaining: {pending}")
            break

        # Check approved folder
        if config.DRIVE_05_REVIEW_APPROVED:
            for item in drive_list(config.DRIVE_05_REVIEW_APPROVED):
                name = item.get("name", "")
                for slug in list(pending):
                    if slug in name:
                        approved.append(slug)
                        pending.discard(slug)

        # Check rejected folder
        if config.DRIVE_05_REVIEW_REJECTED:
            for item in drive_list(config.DRIVE_05_REVIEW_REJECTED):
                name = item.get("name", "")
                for slug in list(pending):
                    if slug in name:
                        rejected.append(slug)
                        pending.discard(slug)

        if pending:
            print(f"  Waiting for review decisions ({len(pending)} pending)... "
                  f"sleeping {config.REVIEW_POLL_INTERVAL_MIN} min")
            time.sleep(interval)

    return {"approved": approved, "rejected": rejected, "still_pending": list(pending)}


# ─── Phase 6: Etsy Draft Upload ───────────────────────────────────────────────

def run_phase_6(
    subject: dict,
    phase3_result: dict | None = None,
    phase4_result: dict | None = None,
    metadata_path: str | None = None,
    output_dir: str = "./output",
    save_to_drive: bool = True,
) -> dict:
    """
    Create a draft Etsy listing for an approved subject.
    NEVER sets listing state to active — agent stops before publish.

    Reads listing data from metadata.json (generated in Phase 3).
    Attaches 3 mockup images (ranked 1–3) and the delivery.zip.
    Writes draft record to Drive /06-audit/drafts/{slug}.json.
    Sends email + Slack with the Etsy draft URL for human to review and publish.

    Args:
        subject:       Subject dict from Phase 2 (title, description, tags, price_usd, etc.)
        phase3_result: run_phase_3() result (raw_image, mockups paths, metadata_path)
        phase4_result: run_phase_4() result (zip_path)
        metadata_path: Path to metadata.json (overrides phase3_result lookup)
        output_dir:    Local root for draft records
        save_to_drive: Write draft record to Drive /06-audit/drafts/

    Returns:
        {
            subject_id:   str,
            listing_id:   int,
            draft_url:    str,
            images_uploaded: int,
            file_uploaded: bool,
            drive_draft_id: str | None,
        }
    """
    slug = subject.get("subject_id", "listing")
    print(f"Phase 6 [{slug}]: creating Etsy draft listing...")

    # ── Load metadata ──────────────────────────────────────────────────────────
    meta: dict = {}
    meta_path = metadata_path or (phase3_result or {}).get("metadata_path", "")
    if meta_path and Path(meta_path).exists():
        meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
    # Merge subject fields over metadata (subject is the canonical source for titles/tags)
    title       = subject.get("title_draft", meta.get("title", slug))
    description = subject.get("description", meta.get("description", ""))
    tags        = subject.get("etsy_tags", meta.get("etsy_tags", []))
    price_usd   = subject.get("price_usd",  meta.get("price_usd", config.DEFAULT_PRICE_USD))

    # Normalise tags — Claude may return nested lists, dicts, or strings
    if tags and isinstance(tags[0], list):
        tags = [t for sublist in tags for t in sublist]
    normalised = []
    for t in tags:
        if isinstance(t, dict):
            t = t.get("tag") or t.get("name") or next(iter(t.values()), "")
        tag = str(t).strip()
        if tag:
            normalised.append(tag[:20])  # Etsy hard limit: 20 chars per tag
    tags = normalised

    # ── Create draft listing ───────────────────────────────────────────────────
    listing_result = create_draft_listing(
        title=title,
        description=description,
        price_usd=float(price_usd),
        tags=tags,
    )
    if "error" in listing_result:
        return {"error": f"create_draft_listing failed: {listing_result['error']}", "subject_id": slug}

    listing_id = listing_result["listing_id"]
    draft_url  = listing_result["draft_url"]
    print(f"  [OK] Draft created: {draft_url}")

    # ── Upload mockup images ───────────────────────────────────────────────────
    mockups_dir = Path(output_dir) / "images" / slug / "mockups"
    mockup_paths = []

    # Prefer phase3_result mockup paths; accept any key names (product_shot /
    # living_room / flat_lay / office / bedroom — depends on which mockup
    # generation run produced the listing)
    if phase3_result and "mockups" in phase3_result:
        m = phase3_result["mockups"]
        for key, p in m.items():
            if key == "cost":
                continue
            if p and Path(str(p)).exists():
                mockup_paths.append(str(p))

    if not mockup_paths and mockups_dir.exists():
        mockup_paths = sorted([str(p) for p in mockups_dir.glob("*.png")])[:3]

    images_uploaded = 0
    for rank, mp in enumerate(mockup_paths[:3], start=1):
        img_result = upload_listing_image(listing_id=listing_id, image_path=mp, rank=rank)
        if "error" in img_result:
            print(f"  [FAIL] Image upload rank {rank} failed: {img_result['error']}")
        else:
            images_uploaded += 1
            print(f"  [OK] Image rank {rank} uploaded")

    # ── Attach delivery.zip ────────────────────────────────────────────────────
    file_uploaded = False
    zip_path = (phase4_result or {}).get("zip_path", "")
    if not zip_path:
        # Try conventional location
        zip_candidate = Path(output_dir) / "packages" / slug / f"{slug}-delivery.zip"
        if zip_candidate.exists():
            zip_path = str(zip_candidate)

    if zip_path and Path(zip_path).exists():
        file_result = upload_listing_file(listing_id=listing_id, file_path=zip_path)
        if "error" in file_result:
            print(f"  [FAIL] ZIP upload failed: {file_result['error']}")
        else:
            file_uploaded = True
            print(f"  [OK] delivery.zip uploaded ({file_result.get('filesize_bytes', '?')} bytes)")
    else:
        print(f"  [!] delivery.zip not found -- attach manually before publishing")

    # ── Write draft record ─────────────────────────────────────────────────────
    draft_record = {
        "subject_id":      slug,
        "listing_id":      listing_id,
        "draft_url":       draft_url,
        "title":           title,
        "images_uploaded": images_uploaded,
        "file_uploaded":   file_uploaded,
        "created_at":      datetime.now(timezone.utc).isoformat(),
        "status":          "draft_live",
    }

    output_path = Path(output_dir) / "audit" / "drafts"
    output_path.mkdir(parents=True, exist_ok=True)
    record_path = output_path / f"{slug}-draft.json"
    record_path.write_text(json.dumps(draft_record, indent=2))

    drive_draft_id = None
    if save_to_drive and config.DRIVE_06_AUDIT_DRAFTS:
        r = drive_write(str(record_path), config.DRIVE_06_AUDIT_DRAFTS)
        drive_draft_id = r.get("file_id")
        print(f"  [OK] Draft record saved to Drive /06-audit/drafts/")

    # ── Notify human ──────────────────────────────────────────────────────────
    review_email = os.environ.get("HUMAN_REVIEW_EMAIL", os.environ.get("GMAIL_ADDRESS", ""))
    _notify_draft_ready(slug, draft_url, images_uploaded, file_uploaded, review_email)

    return {
        "subject_id":      slug,
        "listing_id":      listing_id,
        "draft_url":       draft_url,
        "images_uploaded": images_uploaded,
        "file_uploaded":   file_uploaded,
        "drive_draft_id":  drive_draft_id,
    }


def _notify_draft_ready(
    slug: str, draft_url: str, images_uploaded: int, file_uploaded: bool, to_email: str
) -> None:
    """Send email + Slack when an Etsy draft is ready for human review."""
    body = f"""
<h2>Etsy Draft Ready — {slug}</h2>
<p>Your listing has been created as a draft on Etsy. Please review and publish when ready.</p>
<p><strong><a href="{draft_url}">Open Draft in Etsy Shop Manager →</a></strong></p>
<h3>Upload summary:</h3>
<ul>
  <li>Images uploaded: {images_uploaded}/3</li>
  <li>Delivery ZIP: {'attached' if file_uploaded else 'NOT attached -- upload manually'}</li>
</ul>
<p><em>Reminder: The agent never publishes listings. Click "Publish" in Etsy when ready.</em></p>
"""
    if to_email:
        send_email(to=to_email, subject=f"[Etsy] Draft ready to publish — {slug}", body_html=body)

    slack_text = (
        f"🛍 *Etsy draft ready* — `{slug}`\n"
        f"<{draft_url}|Open in Etsy Shop Manager>\n"
        f"Images: {images_uploaded}/3 | ZIP: {'attached' if file_uploaded else 'MISSING'}"
    )
    send_slack(text=slack_text)


def poll_for_publish(
    draft_records: list[dict],
    timeout_minutes: int = 1440,  # 24 hours
) -> dict:
    """
    Poll Etsy every PUBLISH_POLL_INTERVAL_MIN minutes until all draft listings
    are detected as active (published by human), or timeout is reached.

    Returns {published: [{slug, listing_id, url}], still_draft: [slugs]}.
    """
    pending   = {r["listing_id"]: r["subject_id"] for r in draft_records}
    published = []
    start     = datetime.now(timezone.utc)
    interval  = config.PUBLISH_POLL_INTERVAL_MIN * 60

    while pending:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() / 60
        if elapsed > timeout_minutes:
            print(f"  [!] poll_for_publish timed out. Still draft: {list(pending.values())}")
            break

        active_listings = get_shop_listings(state="active")
        active_ids = {l["listing_id"] for l in active_listings}

        for listing_id in list(pending):
            if listing_id in active_ids:
                slug = pending.pop(listing_id)
                url = next((l["url"] for l in active_listings if l["listing_id"] == listing_id), "")
                published.append({"slug": slug, "listing_id": listing_id, "url": url})
                print(f"  [OK] Published: {slug} → {url}")

        if pending:
            print(f"  Waiting for human to publish ({len(pending)} draft(s))... "
                  f"sleeping {config.PUBLISH_POLL_INTERVAL_MIN} min")
            time.sleep(interval)

    return {"published": published, "still_draft": list(pending.values())}


# ─── Phase 7: Stub ────────────────────────────────────────────────────────────

def run_phase_7(subject: dict) -> dict:
    """Create Pinterest pin, Etsy Ads, social posts. Sprint 5."""
    raise NotImplementedError("Phase 7 is a Sprint 5 feature.")
