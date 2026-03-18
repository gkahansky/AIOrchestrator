"""
Unit tests for platform/registry/tool_router.py
"""

import pytest

from aiplatform.registry.tool_router import select_tool, list_active_tools


def test_select_default_image_generation():
    tool = select_tool("image-generation")
    assert tool["active"] is True
    assert tool["id"] == "dalle3"


def test_explicit_override():
    tool = select_tool("image-generation", tool_id="dalle3")
    assert tool["id"] == "dalle3"


def test_inactive_tool_override_raises():
    with pytest.raises(ValueError, match="not active"):
        select_tool("image-generation", tool_id="gemini-imagen")


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
