"""Boundary tests for the MCP tool registration/call path.

Unlike tests/test_tool_behavior.py (which calls the tool functions directly
as plain Python callables), these tests go through the actual MCP boundary
via `mcp.call_tool(name, arguments)`. That path is where argument/schema
validation (via pydantic, from each tool's type-annotated signature) and
result serialization (dict -> CallToolResult -> TextContent JSON) actually
happen -- none of that is exercised by calling a tool function directly.

This file is intentionally narrow. It does not re-verify the analytical
correctness already covered in test_tool_behavior.py; it only demonstrates:
  1. a valid call crosses the boundary and its content matches the
     underlying function's return value exactly;
  2. schema validation rejects a malformed argument type;
  3. schema validation rejects a missing required argument;
  4. a business-level "not found" result is a *successful* MCP response,
     not a protocol/schema failure -- these are two different failure modes
     and it would be easy to conflate them.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from land_intelligence_mcp.server import compare_counties, mcp  # noqa: E402
from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402


def _call_tool(name: str, arguments: dict):
    """Run mcp.call_tool synchronously for use in ordinary (non-async) tests."""
    return asyncio.run(mcp.call_tool(name, arguments))


def _text_payload(result) -> dict:
    """Extract and JSON-decode the single TextContent block of a tool result."""
    assert len(result.content) == 1
    return json.loads(result.content[0].text)


def test_valid_call_crosses_boundary_and_matches_direct_call():
    """A valid call succeeds at the MCP boundary and its serialized content
    is identical to calling the underlying Python function directly -- the
    boundary must not alter the payload."""
    result = _call_tool("compare_counties", {"limit": 3})

    assert result.is_error is False
    payload = _text_payload(result)
    assert payload == compare_counties(limit=3)


def test_schema_validation_rejects_malformed_argument_type():
    """A limit that can't be parsed as an int must fail schema validation at
    the MCP boundary, before the tool body ever runs."""
    with pytest.raises(ToolError):
        _call_tool("compare_counties", {"limit": "abc"})


def test_schema_validation_rejects_missing_required_argument():
    """explain_parcel_score requires parcel_id; omitting it must fail schema
    validation at the MCP boundary rather than raising a plain TypeError
    from inside the function body."""
    with pytest.raises(ToolError):
        _call_tool("explain_parcel_score", {})


def test_business_level_not_found_is_a_successful_mcp_response():
    """A tool returning {"error": ...} for a business-level condition (an
    unknown parcel_id) is NOT the same thing as an MCP protocol/schema
    failure: the call must still be a well-formed, non-error MCP response,
    only its payload signals the business error."""
    result = _call_tool("explain_parcel_score", {"parcel_id": "NOPE"})

    assert result.is_error is False
    payload = _text_payload(result)
    assert payload == {"error": "Parcel 'NOPE' not found."}
