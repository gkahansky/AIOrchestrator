"""
Content Studio venture configuration.
Podcast show notes + marketing service settings.
Never import this from platform/skills/ — dependency direction is one-way.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys ─────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# ─── Google Drive folder IDs ──────────────────────────────────────────────────
# Set after running scripts/setup_drive_folders.py (or create manually)
DRIVE_PODCAST_ROOT_ID    = os.getenv("DRIVE_PODCAST_ROOT_ID")
DRIVE_PODCAST_ORDERS_ID  = os.getenv("DRIVE_PODCAST_ORDERS_ID")
DRIVE_PODCAST_SAMPLES_ID = os.getenv("DRIVE_PODCAST_SAMPLES_ID")   # free sample PDFs
DRIVE_PODCAST_REVIEW_ID  = os.getenv("DRIVE_PODCAST_REVIEW_ID")
DRIVE_PODCAST_DELIVERED_ID = os.getenv("DRIVE_PODCAST_DELIVERED_ID")

# ─── Drive folder structure ───────────────────────────────────────────────────
# /PodcastNotes/
#   01-orders/         ← DRIVE_PODCAST_ORDERS_ID
#     {order_id}/      ← created per order by pipeline
#       transcript.txt
#       {order_id}.gdoc  ← the deliverable Google Doc
#   02-review/         ← DRIVE_PODCAST_REVIEW_ID  (future: auto-review tracking)
#   03-delivered/      ← DRIVE_PODCAST_DELIVERED_ID  (future: archived deliveries)

# ─── Service tiers ────────────────────────────────────────────────────────────
TIERS = {
    "starter": {
        "price_usd": 49,
        "delivery_hours": 24,
        "max_duration_min": 60,
        "sections": ["show_notes", "timestamps", "guest_bio"],
        "description": "Show notes + timestamps + guest bio",
    },
    "standard": {
        "price_usd": 79,
        "delivery_hours": 24,
        "max_duration_min": 60,
        "sections": ["show_notes", "timestamps", "guest_bio", "transcript", "social_captions"],
        "description": "Starter + full transcript + 5 social captions",
    },
    "premium": {
        "price_usd": 119,
        "delivery_hours": 48,
        "max_duration_min": 90,
        "sections": [
            "show_notes", "timestamps", "guest_bio",
            "transcript", "social_captions",
            "newsletter_excerpt", "seo_metadata",
        ],
        "description": "Standard + newsletter excerpt + SEO metadata",
    },
}

# ─── Output directory ─────────────────────────────────────────────────────────
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

# ─── Review settings ──────────────────────────────────────────────────────────
AUTO_APPROVE = os.getenv("CONTENT_STUDIO_AUTO_APPROVE", "false").lower() == "true"
AUTO_APPROVE_AFTER = int(os.getenv("CONTENT_STUDIO_AUTO_APPROVE_AFTER", "20"))
REVIEW_POLL_INTERVAL_SEC = 30

# ─── Comms ────────────────────────────────────────────────────────────────────
HUMAN_REVIEW_EMAIL = os.getenv("HUMAN_REVIEW_EMAIL", "")
SLACK_REVIEW_CHANNEL = os.getenv("CONTENT_STUDIO_SLACK_CHANNEL", "#content-studio-review")

# ─── Brand voice cache ────────────────────────────────────────────────────────
BRAND_VOICE_CACHE_ENABLED = os.getenv("BRAND_VOICE_CACHE_ENABLED", "true").lower() == "true"

# ─── Content generation model ─────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 8192
CLAUDE_MAX_TOKENS_PREMIUM = 16000
