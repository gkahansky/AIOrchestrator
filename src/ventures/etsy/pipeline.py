"""
Etsy pipeline — orchestrates the 7-phase flow by chaining platform skills.

Sprint 1: Thin stub. Full implementation begins Sprint 3.
Architecture rule: this file imports from platform/skills/ only — never the reverse.

Phases:
  1  — Idea & Theme Generation    (Sprint 2)
  2  — Subject List Generation    (Sprint 2)
  3  — Image Generation           (Sprint 3)
  4  — Packaging                  (Sprint 3)
  5  — Human Review ★             (Sprint 4)
  6  — Store Upload ★             (Sprint 4)
  7  — Promotion                  (Sprint 5)
"""

# Sprint 3+ imports (uncomment as each phase is implemented):
# from aiplatform.skills.research import web_search, trend_analysis, competitor_scan
# from aiplatform.skills.media import generate_image, resize_image, create_mockup
# from aiplatform.skills.storage import drive_read, drive_write, drive_organise
# from aiplatform.skills.comms import send_email, send_slack, create_pin, schedule_social
# from aiplatform.skills.finance import log_cost, log_revenue
# from aiplatform.skills.packaging import create_zip, generate_pdf
# from ventures.etsy import config


def run_phase_1(run_date: str = None) -> dict:
    """Research and score themes. Output: themes CSV + JSON in /01-research/."""
    raise NotImplementedError("Phase 1 is a Sprint 2 feature.")


def run_phase_2(theme: str) -> dict:
    """Generate 20 subjects for a theme. Output: subjects.json in /02-subjects/."""
    raise NotImplementedError("Phase 2 is a Sprint 2 feature.")


def run_phase_3(subject: dict) -> dict:
    """Generate image, resize to 4 variants, create 3 mockups."""
    raise NotImplementedError("Phase 3 is a Sprint 3 feature.")


def run_phase_4(subject: dict) -> dict:
    """Create delivery ZIP and review-sheet PDF."""
    raise NotImplementedError("Phase 4 is a Sprint 3 feature.")


def run_phase_5_notify(pending_subjects: list[dict]) -> dict:
    """Send human review notification. Executor polls for status changes."""
    raise NotImplementedError("Phase 5 is a Sprint 4 feature.")


def run_phase_6(subject: dict) -> dict:
    """Create Etsy draft listing. NEVER sets state=active."""
    raise NotImplementedError("Phase 6 is a Sprint 4 feature.")


def run_phase_7(subject: dict) -> dict:
    """Create Pinterest pin, activate Etsy Ads, queue social posts."""
    raise NotImplementedError("Phase 7 is a Sprint 5 feature.")
