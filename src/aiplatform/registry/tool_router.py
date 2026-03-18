"""
Tool Router — the ONLY place tool selection logic lives in this codebase.

Selection order (first matching rule wins):
  1. Explicit override — caller passes tool_id='midjourney'
  2. Tier match       — match requested tier to best active tool
  3. Budget cap       — skip if monthly spend exceeds cap (TODO Sprint 6)
  4. Availability     — skip if health-check fails (TODO Sprint 6)
  5. Fallback         — use tier='fallback' tool; if that fails, raise + alert Slack
"""

import importlib
import json
from pathlib import Path
from typing import Any, Callable, Optional

REGISTRY_PATH = Path(__file__).parent / "skills.json"

_TIER_PRIORITY = {"premium": 1, "standard": 2, "fallback": 99}


def _load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def select_tool(
    capability: str,
    tool_id: Optional[str] = None,
    tier: Optional[str] = None,
) -> dict:
    """
    Return the matching tool entry from skills.json.

    Args:
        capability: Top-level key in skills.json (e.g. 'image-generation').
        tool_id:    Explicit override — forces a specific tool regardless of tier.
        tier:       Preferred tier ('premium', 'standard', 'fallback').

    Returns:
        The tool dict from skills.json (includes module, function, cost_per_call).

    Raises:
        ValueError: If the capability is unknown or no active tool is available.
    """
    registry = _load_registry()

    if capability not in registry:
        raise ValueError(f"Unknown capability: '{capability}'. Check platform/registry/skills.json.")

    tools = registry[capability]["tools"]
    active_tools = [t for t in tools if t.get("active")]

    if not active_tools:
        raise ValueError(f"No active tools for capability '{capability}'.")

    # Rule 1 — explicit override
    if tool_id:
        match = next((t for t in tools if t["id"] == tool_id), None)
        if match is None:
            raise ValueError(f"Tool '{tool_id}' not found for capability '{capability}'.")
        if not match.get("active"):
            raise ValueError(f"Tool '{tool_id}' is not active. Set active=true in skills.json.")
        return match

    # Rule 2 — tier match
    if tier:
        tier_matches = [t for t in active_tools if t["tier"] == tier]
        if tier_matches:
            return tier_matches[0]

    # Rules 3 & 4 — budget + availability (stubs for Sprint 6)
    # TODO: integrate with finance/log_cost.py for budget checks
    # TODO: add health-check ping per tool

    # Rule 5 — best active non-fallback, then fallback
    non_fallback = sorted(
        [t for t in active_tools if t["tier"] != "fallback"],
        key=lambda t: _TIER_PRIORITY.get(t["tier"], 50),
    )
    if non_fallback:
        return non_fallback[0]

    fallback = next((t for t in active_tools if t["tier"] == "fallback"), None)
    if fallback:
        return fallback

    raise ValueError(f"No usable tool found for capability '{capability}'.")


def get_tool_function(
    capability: str,
    tool_id: Optional[str] = None,
    tier: Optional[str] = None,
) -> tuple[Callable, dict]:
    """
    Return the callable function and its tool metadata for a given capability.

    Usage:
        fn, tool_meta = get_tool_function('image-generation', tier='premium')
        result = fn(prompt='...', aspect_ratio='1:1')

    Returns:
        (callable, tool_dict)
    """
    tool = select_tool(capability, tool_id=tool_id, tier=tier)
    module = importlib.import_module(tool["module"])
    fn = getattr(module, tool["function"])
    return fn, tool


def list_active_tools(capability: str) -> list[dict]:
    """Return all active tools for a capability, sorted by tier priority."""
    registry = _load_registry()
    if capability not in registry:
        return []
    tools = registry[capability]["tools"]
    return sorted(
        [t for t in tools if t.get("active")],
        key=lambda t: _TIER_PRIORITY.get(t["tier"], 50),
    )
