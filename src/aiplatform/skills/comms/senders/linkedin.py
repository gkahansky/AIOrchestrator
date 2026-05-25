"""LinkedIn send handler — assisted send (deep link) with a native provider slot."""
from __future__ import annotations

from aiplatform.skills.comms.senders import _assisted
from aiplatform.skills.comms.senders.base import SendRequest, SendResult


def _build_deep_link(req: SendRequest) -> str:
    # Best target is the post/profile the lead was found on — the operator can
    # open the conversation or message the author from there.
    if req.deep_link_hint:
        return req.deep_link_hint
    handle = (req.platform_username or "").lstrip("@").strip()
    if handle:
        return f"https://www.linkedin.com/in/{handle}/"
    return "https://www.linkedin.com/messaging/"


def send(req: SendRequest, config: dict | None = None) -> SendResult:
    return _assisted.run(req, config, "linkedin", _build_deep_link)
