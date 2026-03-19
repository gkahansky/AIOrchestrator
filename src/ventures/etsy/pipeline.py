"""
Etsy pipeline — orchestrates the 7-phase flow by chaining platform skills.
Architecture rule: imports from aiplatform/skills/ only — never the reverse.

Phases:
  1  — Idea & Theme Generation    ✓ Sprint 2
  2  — Subject List Generation    ✓ Sprint 2
  3  — Image Generation           Sprint 3
  4  — Packaging                  Sprint 3
  5  — Human Review ★             Sprint 4
  6  — Store Upload ★             Sprint 4
  7  — Promotion                  Sprint 5
"""

import csv
import json
import os
import time
from datetime import date
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
- image_prompt: detailed DALL-E 3 image generation prompt (no aspect ratio flags)
- style_notes: one sentence of art direction (style, colour palette, mood)
- etsy_tags: array of exactly 13 Etsy SEO tags (max 20 chars each, Etsy requirement)
- price_usd: recommended price — one of 4.99, 5.99, or 7.99
- quality_tier: "standard" or "premium"
- status: "pending"

Return a JSON array of 20 objects. No other text."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
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
        for mp in (mockups.get("living_room"), mockups.get("office"), mockups.get("bedroom")):
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
        if k in ("living_room", "office", "bedroom") and p and Path(p).exists()
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


# ─── Phase 5–7: Stubs ────────────────────────────────────────────────────────

def run_phase_5_notify(pending_subjects: list[dict]) -> dict:
    """Send human review notification. Sprint 4."""
    raise NotImplementedError("Phase 5 is a Sprint 4 feature.")


def run_phase_6(subject: dict) -> dict:
    """Create Etsy draft listing. NEVER sets state=active. Sprint 4."""
    raise NotImplementedError("Phase 6 is a Sprint 4 feature.")


def run_phase_7(subject: dict) -> dict:
    """Create Pinterest pin, Etsy Ads, social posts. Sprint 5."""
    raise NotImplementedError("Phase 7 is a Sprint 5 feature.")
