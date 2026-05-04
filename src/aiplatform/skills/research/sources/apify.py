"""Generic Apify actor runner — shared by linkedin and facebook handlers."""
import logging
import os
import time

import requests

log = logging.getLogger(__name__)

_APIFY_BASE = "https://api.apify.com/v2"


def run_actor(actor_id: str, run_input: dict, timeout_secs: int = 120) -> list[dict]:
    """
    Run an Apify actor synchronously and return the dataset items.

    Requires APIFY_API_TOKEN env var.
    Falls back to an empty list (not a hard failure) if the token is missing
    or the actor errors — callers must handle empty results gracefully.
    """
    token = os.environ.get("APIFY_API_TOKEN", "")
    if not token:
        log.warning("APIFY_API_TOKEN not set — skipping actor %s", actor_id)
        return []

    try:
        # Start the actor run
        start_resp = requests.post(
            f"{_APIFY_BASE}/acts/{actor_id}/runs",
            params={"token": token},
            json={"runInput": run_input},
            timeout=30,
        )
        if start_resp.status_code not in (200, 201):
            log.warning("Apify start failed for %s: HTTP %s", actor_id, start_resp.status_code)
            return []

        run_id = start_resp.json().get("data", {}).get("id")
        if not run_id:
            return []

        # Poll for completion
        deadline = time.time() + timeout_secs
        while time.time() < deadline:
            status_resp = requests.get(
                f"{_APIFY_BASE}/actor-runs/{run_id}",
                params={"token": token},
                timeout=15,
            )
            status = status_resp.json().get("data", {}).get("status", "")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            time.sleep(5)
        else:
            log.warning("Apify actor %s timed out after %ds", actor_id, timeout_secs)
            return []

        if status != "SUCCEEDED":
            log.warning("Apify actor %s finished with status %s", actor_id, status)
            return []

        # Fetch dataset items
        dataset_id = status_resp.json().get("data", {}).get("defaultDatasetId", "")
        items_resp = requests.get(
            f"{_APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": token, "format": "json", "limit": 100},
            timeout=30,
        )
        return items_resp.json() if items_resp.status_code == 200 else []

    except Exception as e:
        log.warning("Apify actor %s error: %s", actor_id, e)
        return []
