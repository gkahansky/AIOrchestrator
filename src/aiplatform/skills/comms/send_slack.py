"""
Skill: send_slack
Post a message to a Slack channel via the Bot Token API.

Requires env vars:
    SLACK_BOT_TOKEN   — xoxb-... bot token with chat:write scope
    SLACK_REVIEW_CHANNEL — default channel (e.g. #etsy-review); caller can override

To create a Slack bot:
    api.slack.com/apps → Create App → OAuth & Permissions → chat:write scope
    → Install to workspace → copy Bot User OAuth Token
"""

from __future__ import annotations

import logging
import os

import requests

log = logging.getLogger(__name__)

_SLACK_API = "https://slack.com/api/chat.postMessage"


def send_slack(
    channel: str | None = None,
    text: str = "",
    blocks: list[dict] | None = None,
) -> dict:
    """
    Post a message to a Slack channel.

    Args:
        channel:  Channel name or ID (e.g. "#etsy-review" or "C012AB3CD").
                  Defaults to SLACK_REVIEW_CHANNEL env var.
        text:     Plain-text message (also used as notification fallback for blocks).
        blocks:   Optional Block Kit payload for rich messages.

    Returns:
        {ts, channel} on success, {error} on failure.
    """
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        return {"error": "SLACK_BOT_TOKEN not set in environment."}

    target = channel or os.environ.get("SLACK_REVIEW_CHANNEL", "#etsy-review")

    payload: dict = {"channel": target, "text": text}
    if blocks:
        payload["blocks"] = blocks

    try:
        resp = requests.post(
            _SLACK_API,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10,
        )
        data = resp.json()
        if not data.get("ok"):
            err = data.get("error", "unknown Slack error")
            log.error("send_slack failed: %s", err)
            return {"error": err}

        log.info("Slack message sent to %s", target)
        return {"ts": data.get("ts"), "channel": data.get("channel")}

    except Exception as exc:
        log.error("send_slack exception: %s", exc)
        return {"error": str(exc)}
