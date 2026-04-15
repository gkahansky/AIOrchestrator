"""
Accessibility Audit venture configuration.
"""

import os

# Google Drive folder IDs
DRIVE_ACCESSIBILITY_ORDERS_ID = os.environ.get("DRIVE_ACCESSIBILITY_ORDERS_ID", "")
DRIVE_ACCESSIBILITY_SAMPLES_ID = os.environ.get("DRIVE_ACCESSIBILITY_SAMPLES_ID", "")
DRIVE_ACCESSIBILITY_ROOT_ID = os.environ.get("DRIVE_ACCESSIBILITY_ROOT_ID", "")

# Human review
HUMAN_REVIEW_EMAIL = os.environ.get("HUMAN_REVIEW_EMAIL", "")
AUTO_APPROVE = os.environ.get("AUTO_APPROVE", "false").lower() == "true"

# Tier definitions
TIERS = {
    "single_page": {
        "label": "Single Page",
        "price": 49,
        "pages": 1,
        "delivery_hours": 24,
        "is_sample": True,
    },
    "sample": {
        "label": "Sample",
        "price": 0,
        "pages": 1,
        "delivery_hours": 24,
        "is_sample": True,
    },
    "standard": {
        "label": "Standard",
        "price": 149,
        "pages": 5,
        "delivery_hours": 48,
        "is_sample": False,
    },
    "premium": {
        "label": "Premium",
        "price": 249,
        "pages": 20,
        "delivery_hours": 72,
        "is_sample": False,
    },
}

WORK_DIR_BASE = "/tmp/accessibility_audits"
