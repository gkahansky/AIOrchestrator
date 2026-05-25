"""Facebook send handler — assisted send (deep link) with a native provider slot."""
from __future__ import annotations

from aiplatform.skills.comms.senders import _assisted
from aiplatform.skills.comms.senders.base import SendRequest, SendResult


def _build_deep_link(req: SendRequest) -> str:
    if req.deep_link_hint:
        return req.deep_link_hint
    handle = (req.platform_username or "").strip()
    if handle:
        return f"https://www.facebook.com/{handle}"
    return "https://www.facebook.com/messages/"


def send(req: SendRequest, config: dict | None = None) -> SendResult:
    return _assisted.run(req, config, "facebook", _build_deep_link)
