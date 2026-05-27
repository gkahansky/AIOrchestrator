"""
Provider slot for native (API-backed) social lead search.

Public scrapers (Apify actors, Google fallback) return limited, login-walled
data and break often. When a paid session/API provider is wired up (e.g. Unipile
for LinkedIn people search, or a Sales-Navigator/Apify people-search adapter),
add an adapter module here exposing `search(keywords, config) -> list[RawPost]`
and return it from `resolve_provider` for the relevant platform. Nothing else in
the registry, handlers, worker, or router changes.

Mirrors the send-side slot in `skills/comms/senders/providers`.
"""
from __future__ import annotations

from typing import Any


def resolve_provider(platform: str, config: dict | None) -> Any | None:
    """Return a search-provider adapter for `platform`, or None to use the
    handler's default (Apify/Google) search.

    A provider adapter is any object with a `search(keywords, config) ->
    list[RawPost]` method. Selection can be driven by `config` (per-source/
    campaign) once a provider is integrated. Returns None today.
    """
    return None
