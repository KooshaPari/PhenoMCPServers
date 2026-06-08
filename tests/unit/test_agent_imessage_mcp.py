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


def test_notify_user_defaults_to_koosha_role(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp, "call_agent_imessage", lambda args: calls.append(args) or {"ok": True})

    assert mcp.tool_call("notify_user", {"message": "hello"}) == {"ok": True}

    assert calls == [["notify", "--recipient", "koosha", "hello"]]


def test_notify_user_accepts_only_scoped_recipient_roles(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp, "call_agent_imessage", lambda args: calls.append(args) or {"ok": True})

    assert mcp.tool_call("notify_user", {"recipient": "sponsor", "message": "hello", "dry_run": True}) == {"ok": True}

    assert calls == [["notify", "--recipient", "sponsor", "hello", "--dry-run"]]
    with pytest.raises(ValueError):
        mcp.tool_call("notify_user", {"recipient": "random-contact", "message": "hello"})


def test_wait_for_user_reply_forwards_scoped_recipient(monkeypatch) -> None:
    calls = []

    def fake_call(args, timeout=60):
        calls.append((args, timeout))
        return {"ok": True}

    monkeypatch.setattr(mcp, "call_agent_imessage", fake_call)

    assert mcp.tool_call("wait_for_user_reply", {"recipient": "sponsor", "timeout": 5, "poll": 0.1}) == {"ok": True}

    assert calls == [
        (
            ["wait", "--recipient", "sponsor", "--timeout", "5", "--poll", "0.1", "--json"],
            25,
        )
    ]


def test_session_tools_are_exposed() -> None:
    names = {tool["name"] for tool in mcp.TOOLS}

    assert {"sessions", "session_heartbeat", "session_event", "session_scan", "session_events"} <= names
    # New poll-* tools are also exposed so Codex/Claude can read iMessage events
    # directly from the MCP server.
    assert {"poll_user_response", "poll_read_receipts"} <= names


def test_poll_user_response_returns_empty_events_when_imessage_unavailable(monkeypatch) -> None:
    from agent_user_status import agent_imessage_mcp_sessions as mcp_sessions

    monkeypatch.setattr(mcp_sessions, "is_imessage_available", lambda: False)
    invoked = []
    monkeypatch.setattr(
        mcp,
        "call_agent_imessage",
        lambda args: invoked.append(args) or {"ok": True},
    )

    result = mcp.tool_call("poll_user_response", {"since": "2026-06-08T00:00:00Z"})

    assert result == {"ok": True, "events": []}
    assert invoked == []  # must not spawn agent-imessage when disabled


def test_poll_read_receipts_returns_empty_events_when_imessage_unavailable(monkeypatch) -> None:
    from agent_user_status import agent_imessage_mcp_sessions as mcp_sessions

    monkeypatch.setattr(mcp_sessions, "is_imessage_available", lambda: False)
    invoked = []
    monkeypatch.setattr(
        mcp,
        "call_agent_imessage",
        lambda args: invoked.append(args) or {"ok": True},
    )

    result = mcp.tool_call("poll_read_receipts", {})

    assert result == {"ok": True, "events": []}
    assert invoked == []


def test_poll_user_response_forwards_since_to_cli(monkeypatch) -> None:
    from agent_user_status import agent_imessage_mcp_sessions as mcp_sessions

    monkeypatch.setattr(mcp_sessions, "is_imessage_available", lambda: True)
    captured = []
    monkeypatch.setattr(
        mcp,
        "call_agent_imessage",
        lambda args: captured.append(args) or {"ok": True, "events": []},
    )

    rc = mcp.tool_call("poll_user_response", {"since": "2026-06-08T00:00:00Z"})

    assert rc == {"ok": True, "events": []}
    assert captured == [["user-responses", "--since", "2026-06-08T00:00:00Z"]]


def test_poll_read_receipts_forwards_since_to_cli(monkeypatch) -> None:
    from agent_user_status import agent_imessage_mcp_sessions as mcp_sessions

    monkeypatch.setattr(mcp_sessions, "is_imessage_available", lambda: True)
    captured = []
    monkeypatch.setattr(
        mcp,
        "call_agent_imessage",
        lambda args: captured.append(args) or {"ok": True, "events": []},
    )

    rc = mcp.tool_call("poll_read_receipts", {"since": "2026-06-08T00:00:00Z"})

    assert rc == {"ok": True, "events": []}
    assert captured == [["read-receipts", "--since", "2026-06-08T00:00:00Z"]]


def test_session_heartbeat_tool_forwards_structured_cli_event(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp, "call_agent_imessage", lambda args: calls.append(args) or {"ok": True})

    result = mcp.tool_call(
        "session_heartbeat",
        {
            "session_id": "codex-123",
            "agent": "codex",
            "status": "working",
            "state": "implementation",
            "repo": "agent-user-status",
            "ttl_seconds": 60,
        },
    )

    assert result == {"ok": True}
    assert calls == [
        [
            "session-heartbeat",
            "--session-id",
            "codex-123",
            "--agent",
            "codex",
            "--status",
            "working",
            "--ttl-seconds",
            "60",
            "--state",
            "implementation",
            "--repo",
            "agent-user-status",
        ]
    ]


def test_session_events_tool_forwards_filters(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp, "call_agent_imessage", lambda args: calls.append(args) or {"ok": True})

    assert mcp.tool_call("session_events", {"session_id": "codex-123", "kind": "event", "limit": 5}) == {"ok": True}

    assert calls == [["session-events", "--limit", "5", "--kind", "event", "--session-id", "codex-123"]]
