from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MCP_PATH = Path(__file__).resolve().parents[2] / "src" / "mcp" / "agent_imessage_mcp.py"
SPEC = importlib.util.spec_from_file_location("agent_imessage_mcp_under_test", MCP_PATH)
assert SPEC and SPEC.loader
mcp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mcp)


def test_redact_agent_payload_removes_status_preview_and_chat() -> None:
    payload = {
        "ok": True,
        "data": {
            "mode": "near",
            "latest_inbound_preview": "private message text",
            "chat": {"id": "private-chat"},
        },
    }

    redacted = mcp.redact_agent_payload(payload)

    assert redacted["data"] == {"mode": "near"}


def test_user_status_tool_redacts_cli_status(monkeypatch) -> None:
    monkeypatch.setattr(
        mcp,
        "call_agent_imessage",
        lambda _args: {
            "ok": True,
            "data": {
                "mode": "near",
                "latest_inbound_preview": "private message text",
                "chat": {"id": "private-chat"},
            },
        },
    )

    result = mcp.tool_call("user_status", {})

    assert result["data"] == {"mode": "near"}


def test_generic_messages_mcp_requires_explicit_admin_env(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_IMESSAGE_ALLOW_GENERIC_MESSAGES_MCP", raising=False)
    args = type("Args", (), {"client": "both", "with_messages": True})()

    with pytest.raises(SystemExit):
        mcp.command_install(args)
