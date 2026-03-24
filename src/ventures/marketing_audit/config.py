"""
Marketing Audit venture configuration.
Never import this from platform/skills/ — dependency direction is one-way.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Service tiers ────────────────────────────────────────────────────────────
TIERS = {
    "snapshot": {
        "price_usd": 49,
        "delivery_hours": 24,
        "competitors": 0,
        "depth": "snapshot",
        "description": "Overall score + top 5 quick wins, PDF",
    },
    "full": {
        "price_usd": 149,
        "delivery_hours": 48,
        "competitors": 2,
        "depth": "full",
        "description": "6 dimensions + 2 competitor comparison + copy examples, PDF",
    },
    "premium": {
        "price_usd": 249,
        "delivery_hours": 72,
        "competitors": 3,
        "depth": "premium",
        "description": "Full audit + 30-day roadmap + 3 competitors, PDF",
    },
}

# ─── Scoring weights (must sum to 1.0) ────────────────────────────────────────
DIMENSION_WEIGHTS = {
    "Content & Messaging":    0.25,
    "Conversion Optimization": 0.20,
    "SEO & Discoverability":  0.20,
    "Competitive Positioning": 0.15,
    "Brand & Trust":          0.10,
    "Growth & Strategy":      0.10,
}

DIMENSION_WEIGHT_LABELS = {
    "Content & Messaging":    "25%",
    "Conversion Optimization": "20%",
    "SEO & Discoverability":  "20%",
    "Competitive Positioning": "15%",
    "Brand & Trust":          "10%",
    "Growth & Strategy":      "10%",
}

# ─── Google Drive ─────────────────────────────────────────────────────────────
DRIVE_AUDIT_ROOT_ID = os.getenv("DRIVE_AUDIT_ROOT_ID")

# ─── Review & delivery ────────────────────────────────────────────────────────
HUMAN_REVIEW_EMAIL = os.getenv("HUMAN_REVIEW_EMAIL", "")
AUTO_APPROVE = os.getenv("AUDIT_AUTO_APPROVE", "false").lower() == "true"
COMPETITOR_MAX = int(os.getenv("COMPETITOR_MAX", "3"))

# ─── Paths ────────────────────────────────────────────────────────────────────
# Set this to C:\Projects\AI\ai-marketing-claude (or wherever the repo lives)
AI_MARKETING_CLAUDE_PATH = os.getenv("AI_MARKETING_CLAUDE_PATH", "")

# ─── Claude ───────────────────────────────────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 8192
