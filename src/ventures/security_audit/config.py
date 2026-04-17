"""
Security Audit venture configuration.
"""

import os
from typing import Optional

# ── Fernet encryption helpers ──────────────────────────────────────────────────
# auth_password is encrypted at rest using Fernet symmetric encryption.
# Set FERNET_KEY in the environment (generate once with: Fernet.generate_key()).
# If the key is absent, passwords are stored as plaintext with a warning (graceful
# degradation so existing rows and test environments continue to work).

_FERNET_KEY: str = os.environ.get("FERNET_KEY", "")
_fernet = None

def _get_fernet():
    global _fernet
    if _fernet is None and _FERNET_KEY:
        from cryptography.fernet import Fernet
        _fernet = Fernet(_FERNET_KEY.encode() if isinstance(_FERNET_KEY, str) else _FERNET_KEY)
    return _fernet


def encrypt_password(plaintext: Optional[str]) -> Optional[str]:
    """
    Encrypt a password for storage. Returns None if input is None.
    If FERNET_KEY is not configured, returns the plaintext unchanged
    (graceful degradation — log a warning in prod).
    """
    if plaintext is None:
        return None
    f = _get_fernet()
    if f is None:
        import warnings
        warnings.warn(
            "FERNET_KEY not set — auth_password stored as plaintext. "
            "Set FERNET_KEY in production.",
            stacklevel=2,
        )
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_password(ciphertext: Optional[str]) -> Optional[str]:
    """
    Decrypt a stored password. Returns None if input is None.
    Handles both encrypted ciphertext and legacy plaintext rows gracefully:
    if decryption fails (e.g. pre-migration plaintext), returns the value as-is.
    """
    if ciphertext is None:
        return None
    f = _get_fernet()
    if f is None:
        return ciphertext  # no key — return as stored
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Legacy plaintext row — return as-is (migration grace period)
        return ciphertext


# Google Drive folder IDs
# DRIVE_SECURITY_ROOT_ID    — parent folder (fallback if specific folders not set)
# DRIVE_SECURITY_ORDERS_ID  — full/paid report PDFs
# DRIVE_SECURITY_SAMPLES_ID — sample/teaser PDFs (future)
DRIVE_SECURITY_ROOT_ID    = os.environ.get("DRIVE_SECURITY_ROOT_ID", "")
DRIVE_SECURITY_ORDERS_ID  = os.environ.get("DRIVE_SECURITY_ORDERS_ID", "") or DRIVE_SECURITY_ROOT_ID
DRIVE_SECURITY_SAMPLES_ID = os.environ.get("DRIVE_SECURITY_SAMPLES_ID", "") or DRIVE_SECURITY_ROOT_ID

# Human review
HUMAN_REVIEW_EMAIL = os.environ.get("HUMAN_REVIEW_EMAIL", "")
AUTO_APPROVE = os.environ.get("AUTO_APPROVE", "false").lower() == "true"

# External API keys (optional — phases degrade gracefully without them)
HIBP_API_KEY = os.environ.get("HIBP_API_KEY", "")
# Censys now uses a single bearer token (not ID+Secret)
CENSYS_API_KEY = os.environ.get("CENSYS_API_KEY", "")

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
        "phases": [1, 2, 3, 4],       # Phase 4 exploit testing; Phase 5 runs conditionally when credentials supplied
        "authenticated": True,
        "delivery_hours": 6,
        "report_pages": "10-15",
    },
    "agency": {
        "label": "Agency",
        "price": 349,
        "phases": [1, 2, 3, 4],       # Phase 4 exploit testing; Phase 5 runs conditionally when credentials supplied
        "authenticated": True,
        "delivery_hours": 3,
        "report_pages": "15-25",
        "multi_subdomain": True,
    },
}
