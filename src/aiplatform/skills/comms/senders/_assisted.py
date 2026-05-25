"""
Shared assisted-send runner for social platforms.

Assisted send: there is no official cold-DM API for LinkedIn / Instagram /
Facebook, so the handler generates the message + a deep link to the conversation
or profile. The operator opens the link, sends in the native app, then confirms
in planBadmin — which is what finalises the send and logs it to contact history.

A platform handler calls `run(req, config, platform, build_deep_link)`. If a
native provider is configured for that platform it is used instead (see
senders.providers.resolve_provider).
"""
from __future__ import annotations

from typing import Callable

from aiplatform.skills.comms.senders.base import SendRequest, SendResult
from aiplatform.skills.comms.senders.providers import resolve_provider


def run(
    req: SendRequest,
    config: dict | None,
    platform: str,
    build_deep_link: Callable[[SendRequest], str],
) -> SendResult:
    provider = resolve_provider(platform, config)
    if provider is not None:
        return provider.send(req, config)

    deep_link = build_deep_link(req)
    return SendResult(
        status="awaiting_manual",
        provider="manual",
        deep_link=deep_link,
        instructions=(
            f"Open the {platform.title()} link, paste the message, send it, "
            "then click 'Mark as sent' to log it."
        ),
    )
