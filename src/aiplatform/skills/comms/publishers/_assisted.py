"""
Shared assisted-publish runner.

Assisted publish: the publisher returns `awaiting_manual` plus a deep link to
the channel's composer/admin tool, pre-filled where possible. The operator
opens the link, posts in the native app, then confirms in planBadmin — which
finalises the PublishJob and writes the external URL.

Used as a fallback by every channel handler when no OAuth token / API access
is configured for that (brand × channel) pair.
"""
from __future__ import annotations

from typing import Callable

from aiplatform.skills.comms.publishers.base import PublishRequest, PublishResult


def run(
    req: PublishRequest,
    channel: str,
    build_deep_link: Callable[[PublishRequest], str],
) -> PublishResult:
    deep_link = build_deep_link(req)
    return PublishResult(
        status="awaiting_manual",
        provider="manual",
        deep_link=deep_link,
        instructions=(
            f"Open the {channel.replace('_', ' ').title()} link, paste the post, "
            "publish it, then click 'Mark as published' to log it."
        ),
    )
