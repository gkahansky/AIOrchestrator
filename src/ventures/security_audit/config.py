"""
Security Audit venture configuration.
"""

import os

# Google Drive
DRIVE_SECURITY_REPORTS_ID = os.environ.get("DRIVE_SECURITY_REPORTS_ID", "")
DRIVE_SECURITY_ROOT_ID = os.environ.get("DRIVE_SECURITY_ROOT_ID", "")

# Human review
HUMAN_REVIEW_EMAIL = os.environ.get("HUMAN_REVIEW_EMAIL", "")
AUTO_APPROVE = os.environ.get("AUTO_APPROVE", "false").lower() == "true"

# External API keys (optional — phases degrade gracefully without them)
HIBP_API_KEY = os.environ.get("HIBP_API_KEY", "")
CENSYS_API_ID = os.environ.get("CENSYS_API_ID", "")
CENSYS_API_SECRET = os.environ.get("CENSYS_API_SECRET", "")

# Scan rate limiting — max requests per second to any single host
MAX_REQUESTS_PER_SECOND = int(os.environ.get("SECURITY_MAX_RPS", "2"))

# Work directory for PDF generation
WORK_DIR_BASE = "/tmp/security_audits"

# Service tiers
TIERS = {
    "starter": {
        "label": "Starter",
        "price": 49,
        "phases": [1, 2, 3],          # Passive OSINT + surface + header/TLS/CORS
        "authenticated": False,
        "delivery_hours": 4,
        "report_pages": "5-10",
    },
    "professional": {
        "label": "Professional",
        "price": 149,
        "phases": [1, 2, 3, 5],       # + authenticated Playwright testing (Phase 5)
        "authenticated": True,
        "delivery_hours": 6,
        "report_pages": "10-15",
    },
    "agency": {
        "label": "Agency",
        "price": 349,
        "phases": [1, 2, 3, 5],       # + multi-subdomain scope
        "authenticated": True,
        "delivery_hours": 3,
        "report_pages": "15-25",
        "multi_subdomain": True,
    },
}
