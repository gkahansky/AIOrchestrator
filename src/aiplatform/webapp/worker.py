"""
Thin re-export — canonical worker lives at aiplatform.worker.

Existing imports of `aiplatform.webapp.worker` continue to work unchanged.
"""

from aiplatform.worker import (  # noqa: F401  re-export
    celery_app,
    run_etsy_phase,
    run_audit_order,
    run_podcast_order,
)
