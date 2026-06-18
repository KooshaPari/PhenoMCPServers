"""pytest: forge3-bridge MCP server smoke tests.

Verifies the server responds to MCP initialize + tools/list and can execute one
real tool call (forge3_doctor) against the local forge3 binary.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SERVER = REPO / "forge3_bridge_server.py"


def _run_mcp(messages: list[dict], timeout: int = 30) -> list[dict]:
    """Spawn the MCP server, send JSON-RPC messages, parse replies."""
    input_lines = "\n".join(json.dumps(m) for m in messages) + "\n"
    proc = subprocess.run(
        [sys.executable, str(SERVER)],
        input=input_lines,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO),
    )
    # Server replies are JSON-RPC envelopes on stdout; pick them out and ignore
    # any FastMCP banner lines.
    replies = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            replies.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return replies


def test_server_responds_to_initialize_and_tools_list():
    """Server returns initialize result + a tools/list with all 15 tools."""
    replies = _run_mcp([
        {"jsonrpc": "2.0", "id": "t1", "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.0.1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": "t2", "method": "tools/list"},
    ])
    assert len(replies) == 2, f"expected 2 JSON-RPC replies, got {len(replies)}"

    init = replies[0]
    assert init["id"] == "t1"
    assert "result" in init
    assert init["result"]["serverInfo"]["name"] == "forge3-bridge"

    tools = replies[1]
    assert tools["id"] == "t2"
    tool_names = [t["name"] for t in tools["result"]["tools"]]
    expected = {"forge3_info", "forge3_doctor", "forge3_methods", "forge3_tools",
                "forge3_extensions", "forge3_models", "forge3_agents",
                "forge3_commands", "forge3_call", "forge3_shell", "forge3_search",
                "forge3_read", "forge3_write", "forge3_patch", "forge3_skill_search"}
    missing = expected - set(tool_names)
    assert not missing, f"missing tools: {missing}"
    assert len(tool_names) >= 15


@pytest.mark.skipif(
    not os.path.exists(os.environ.get("FORGE3_BIN", "/Users/kooshapari/.cargo/bin/forge3")),
    reason="forge3 binary not available",
)
def test_doctor_tool_call_against_real_daemon():
    """Real forge3_doctor call returns a verdict dict."""
    replies = _run_mcp([
        {"jsonrpc": "2.0", "id": "d1", "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.0.1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": "d2", "method": "tools/call",
         "params": {"name": "forge3_doctor", "arguments": {}}},
    ])
    call_reply = replies[-1]
    assert call_reply["id"] == "d2"
    assert "result" in call_reply
    result = call_reply["result"]
    # FastMCP 2.x envelope: prefer structuredContent (already a dict), fall
    # back to parsing the first TextContent item's text payload.
    if isinstance(result, dict) and "structuredContent" in result:
        parsed = result["structuredContent"]
    else:
        content = result.get("content", [])
        text = content[0]["text"] if isinstance(content, list) and content else json.dumps(result)
        parsed = json.loads(text)
    assert "binary" in parsed
    assert "recommendation" in parsed