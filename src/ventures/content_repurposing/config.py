"""
Content Repurposing venture configuration.
Unified Service B+C: short clips + thumbnails + text artifacts per plan.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ─── Plan definitions ─────────────────────────────────────────────────────────
# Each plan specifies both media outputs (clips/thumbnails) and text artifacts.

PLANS = {
    "free": {
        "price_usd":         0,
        "uploads_per_month": 1,
        "max_duration_min":  30,
        "clips":             3,
        "watermark":         True,
        "social_scheduling": False,
        "creatomate_templates": False,
        # Text artifacts included at this tier:
        "text_outputs":      ["captions"],
        "caption_platforms": ["linkedin", "instagram", "twitter"],
        "captions_per_platform": 2,
        "blog_word_range":   None,
        "newsletter_word_range": None,
        "brand_voice_injection": False,
        "description": "3 watermarked clips + captions (download only)",
    },
    "starter": {
        "price_usd":         29,
        "uploads_per_month": 10,
        "max_duration_min":  60,
        "clips":             5,
        "watermark":         False,
        "social_scheduling": False,
        "creatomate_templates": False,
        "text_outputs":      ["captions", "transcript", "show_notes"],
        "caption_platforms": ["linkedin", "instagram", "twitter"],
        "captions_per_platform": 3,
        "blog_word_range":   None,
        "newsletter_word_range": None,
        "brand_voice_injection": False,
        "description": "5 clips + transcript + show notes + captions (3 platforms)",
    },
    "pro": {
        "price_usd":         79,
        "uploads_per_month": 40,
        "max_duration_min":  120,
        "clips":             10,
        "watermark":         False,
        "social_scheduling": True,
        "creatomate_templates": False,
        "text_outputs":      ["captions", "transcript", "show_notes", "blog_post", "newsletter"],
        "caption_platforms": ["linkedin", "instagram", "twitter", "tiktok", "youtube"],
        "captions_per_platform": 5,
        "blog_word_range":   (800, 1200),
        "newsletter_word_range": (300, 500),
        "brand_voice_injection": False,
        "description": "10 clips + all text artifacts + Buffer scheduling (5 platforms)",
    },
    "studio": {
        "price_usd":         199,
        "uploads_per_month": None,   # unlimited
        "max_duration_min":  240,
        "clips":             20,
        "watermark":         False,
        "social_scheduling": True,
        "creatomate_templates": True,
        "text_outputs":      [
            "captions", "transcript", "show_notes",
            "blog_post", "newsletter",
            "linkedin_longform", "youtube_description",
        ],
        "caption_platforms": ["linkedin", "instagram", "twitter", "tiktok", "youtube"],
        "captions_per_platform": 5,
        "blog_word_range":   (1200, 1800),
        "newsletter_word_range": (400, 600),
        "brand_voice_injection": True,
        "description": "20 clips + Creatomate templates + all text + scheduling",
    },
}

# ─── Video processing ─────────────────────────────────────────────────────────
SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
MAX_UPLOAD_BYTES = int(os.getenv("CR_MAX_UPLOAD_MB", "2000")) * 1024 * 1024

CLIP_MIN_S = 30
CLIP_MAX_S = 90
VIRALITY_SCORE_THRESHOLD = float(os.getenv("CR_VIRALITY_THRESHOLD", "0.55"))

CLIP_TARGET_FORMAT = "portrait_9_16"   # 1080×1920 — universal reel format

CAPTION_STYLE = {
    "font_size":    int(os.getenv("CR_CAPTION_FONT_SIZE", "64")),    # literal pixels on 1920px video
    "font_color":   os.getenv("CR_CAPTION_FONT_COLOR", "white"),
    "border_color": os.getenv("CR_CAPTION_BORDER_COLOR", "black"),
    "border_width": int(os.getenv("CR_CAPTION_BORDER_WIDTH", "3")),
}

# "standard" = phrase-level captions | "word_pop" = TikTok 2-word kinetic chunks
CAPTION_STYLE_TYPE = os.getenv("CR_CAPTION_STYLE", "word_pop")

# ─── Temp file dir ────────────────────────────────────────────────────────────
CR_TEMP_DIR = os.getenv("CR_TEMP_DIR", "/tmp")

# ─── Drive folder ─────────────────────────────────────────────────────────────
# Reuse the podcast orders folder — each CR job creates a subfolder inside it
DRIVE_CR_ROOT_ID = (
    os.getenv("DRIVE_CR_ROOT_ID")          # explicit override if needed
    or os.getenv("DRIVE_PODCAST_ORDERS_ID", "")  # shared with content_studio
)

# ─── External APIs ────────────────────────────────────────────────────────────
CREATOMATE_API_KEY       = os.getenv("CREATOMATE_API_KEY", "")
CREATOMATE_TEMPLATE_REEL = os.getenv("CREATOMATE_TEMPLATE_REEL", "")
BUFFER_ACCESS_TOKEN      = os.getenv("BUFFER_ACCESS_TOKEN", "")
BUFFER_RATE_LIMIT_PER_MIN = 10

# ─── Model settings ───────────────────────────────────────────────────────────
CLAUDE_MODEL  = "claude-sonnet-4-6"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ─── Review ───────────────────────────────────────────────────────────────────
# Review is handled via planBadmin (approval gate in Redis) — same as all other ventures.
HUMAN_REVIEW_ALWAYS = True
