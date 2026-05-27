"""
Shared provider-first runner for social source handlers.

A handler calls `run(keywords, config, platform, default_search)`. If a native
search provider is configured for that platform it is used; otherwise the
handler's own default (Apify/Google) search runs. Mirrors
`skills/comms/senders/_assisted.run`.
"""
from __future__ import annotations

import logging
from typing import Callable

from aiplatform.skills.research.sources.base import RawPost
from aiplatform.skills.research.sources.providers import resolve_provider

log = logging.getLogger(__name__)


def run(
    keywords: list[str],
    config: dict,
    platform: str,
    default_search: Callable[[list[str], dict], list[RawPost]],
) -> list[RawPost]:
    provider = resolve_provider(platform, config)
    if provider is not None:
        try:
            return provider.search(keywords, config)
        except Exception as e:  # never let a provider error lose the source
            log.warning("search provider for '%s' failed: %s — falling back", platform, e)
    return default_search(keywords, config)
