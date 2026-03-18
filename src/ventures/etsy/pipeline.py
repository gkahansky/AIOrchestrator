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
- target_keywords: array of exactly 5 Etsy SEO keywords
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


# ─── Phase 3–7: Stubs ────────────────────────────────────────────────────────

def run_phase_3(subject: dict) -> dict:
    """Generate image, resize to 4 variants, create 3 mockups. Sprint 3."""
    raise NotImplementedError("Phase 3 is a Sprint 3 feature.")


def run_phase_4(subject: dict) -> dict:
    """Create delivery ZIP and review-sheet PDF. Sprint 3."""
    raise NotImplementedError("Phase 4 is a Sprint 3 feature.")


def run_phase_5_notify(pending_subjects: list[dict]) -> dict:
    """Send human review notification. Sprint 4."""
    raise NotImplementedError("Phase 5 is a Sprint 4 feature.")


def run_phase_6(subject: dict) -> dict:
    """Create Etsy draft listing. NEVER sets state=active. Sprint 4."""
    raise NotImplementedError("Phase 6 is a Sprint 4 feature.")


def run_phase_7(subject: dict) -> dict:
    """Create Pinterest pin, Etsy Ads, social posts. Sprint 5."""
    raise NotImplementedError("Phase 7 is a Sprint 5 feature.")
