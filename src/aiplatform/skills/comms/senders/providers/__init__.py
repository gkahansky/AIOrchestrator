"""
Provider slot for native (automated) social sending.

Today there is no official cold-DM API for LinkedIn / Instagram / Facebook, so
the social handlers fall back to assisted send (deep link + manual confirm).
When a paid unified provider (e.g. Unipile) is wired up, add an adapter module
here exposing `send(req, config) -> SendResult` and return it from
`resolve_provider` for the relevant platform. Nothing else in the registry,
worker, or router changes.
"""
from __future__ import annotations

from typing import Any


def resolve_provider(platform: str, config: dict | None) -> Any | None:
    """Return a provider adapter for `platform`, or None to use assisted send.

    A provider adapter is any object with a `send(req, config) -> SendResult`
    method. Selection can be driven by `config` (per-source/campaign) once a
    provider is integrated. Returns None today.
    """
    return None
