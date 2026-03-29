"""
Etsy venture configuration.
All Etsy-specific settings, Drive folder IDs, and business rules live here.
Never import this from platform/skills/ — dependency direction is one-way.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Etsy API ─────────────────────────────────────────────────────────────────
ETSY_API_KEY = os.getenv("ETSY_API_KEY")
ETSY_API_SECRET = os.getenv("ETSY_API_SECRET")
ETSY_SHOP_ID = os.getenv("ETSY_SHOP_ID")
ETSY_ACCESS_TOKEN = os.getenv("ETSY_ACCESS_TOKEN")
ETSY_REFRESH_TOKEN = os.getenv("ETSY_REFRESH_TOKEN")
ETSY_API_BASE = "https://openapi.etsy.com/v3"

# ─── Google Drive folder IDs ──────────────────────────────────────────────────
DRIVE_ROOT = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID")
DRIVE_01_RESEARCH = os.getenv("DRIVE_01_RESEARCH_ID")
DRIVE_02_SUBJECTS = os.getenv("DRIVE_02_SUBJECTS_ID")
DRIVE_03_IMAGES = os.getenv("DRIVE_03_IMAGES_ID")
DRIVE_04_PACKAGES = os.getenv("DRIVE_04_PACKAGES_ID")
DRIVE_05_REVIEW = os.getenv("DRIVE_05_REVIEW_ID")
DRIVE_05_REVIEW_PENDING = os.getenv("DRIVE_05_REVIEW_PENDING_ID")
DRIVE_05_REVIEW_APPROVED = os.getenv("DRIVE_05_REVIEW_APPROVED_ID")
DRIVE_05_REVIEW_REJECTED = os.getenv("DRIVE_05_REVIEW_REJECTED_ID")
DRIVE_06_AUDIT = os.getenv("DRIVE_06_AUDIT_ID")
DRIVE_06_AUDIT_DRAFTS = os.getenv("DRIVE_06_AUDIT_DRAFTS_ID")
DRIVE_06_AUDIT_PUBLISHED = os.getenv("DRIVE_06_AUDIT_PUBLISHED_ID")
DRIVE_07_PROMO = os.getenv("DRIVE_07_PROMO_ID")

# ─── Output directory ─────────────────────────────────────────────────────────
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

# ─── Pipeline settings ────────────────────────────────────────────────────────
THEME_MIN_SCORE = 60            # Themes below this score are dropped after Phase 1
SUBJECTS_PER_THEME = 20        # Number of subjects generated per theme in Phase 2
REVIEW_POLL_INTERVAL_MIN = 30  # How often Executor polls /05-review/ (minutes)
PUBLISH_POLL_INTERVAL_MIN = 15 # How often Executor polls Etsy for newly active listings

# ─── Pricing rules ────────────────────────────────────────────────────────────
DEFAULT_PRICE_USD = 4.99
PREMIUM_PRICE_USD = 7.99

# ─── Tag requirements ─────────────────────────────────────────────────────────
REQUIRED_TAG_COUNT = 13        # Etsy requires exactly 13 tags per listing
TITLE_MAX_CHARS = 140          # Etsy title character limit

# ─── Listing constraints ──────────────────────────────────────────────────────
MOCKUPS_PER_LISTING = 3
DELIVERY_ZIP_MAX_MB = 20       # Etsy hard limit
