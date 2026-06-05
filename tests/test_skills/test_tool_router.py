"""
Unit tests for platform/registry/tool_router.py
"""

import pytest

from aiplatform.registry.tool_router import select_tool, list_active_tools


def test_select_default_image_generation():
    tool = select_tool("image-generation")
    assert tool["active"] is True
    # Gemini Imagen is the standard-tier primary; gpt-image-1 is the active fallback.
    assert tool["id"] == "gemini-imagen"


def test_explicit_override():
    tool = select_tool("image-generation", tool_id="gpt-image-1")
    assert tool["id"] == "gpt-image-1"


def test_inactive_tool_override_raises():
    # `dalle3` is kept as a legacy slot under image-generation but inactive;
    # explicit override on an inactive tool must raise.
    with pytest.raises(ValueError, match="not active"):
        select_tool("image-generation", tool_id="dalle3")


def test_unknown_capability_raises():
    with pytest.raises(ValueError, match="Unknown capability"):
        select_tool("does-not-exist")


def test_list_active_tools():
    tools = list_active_tools("image-generation")
    assert all(t["active"] for t in tools)
    assert len(tools) >= 1


def test_unknown_capability_returns_empty_list():
    tools = list_active_tools("does-not-exist")
    assert tools == []
