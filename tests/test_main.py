"""Tests for the main entrypoint handler."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))


@pytest.mark.asyncio
async def test_handler_rejects_invalid_step():
    """Handler should reject invalid step names."""
    from main import handler
    result = await handler({"step": "step99"})
    data = json.loads(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_handler_accepts_string_payload():
    """Handler should parse string payloads as JSON."""
    from main import handler
    result = await handler('{"step": "invalid"}')
    data = json.loads(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_handler_rejects_invalid_graph_state():
    """Handler should reject non-dict graph_state."""
    from main import handler
    result = await handler({"step": "step1", "prompt": "test", "graph_state": "not a dict"})
    data = json.loads(result)
    assert "error" in data
    assert "graph_state must be a JSON object" in data["error"]
