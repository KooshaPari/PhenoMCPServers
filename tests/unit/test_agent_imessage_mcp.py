from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MCP_PATH = Path(__file__).resolve().parents[2] / "src" / "mcp" / "agent_imessage_mcp.py"
SPEC = importlib.util.spec_from_file_location("agent_imessage_mcp_under_test", MCP_PATH)
assert SPEC and SPEC.loader
mcp = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mcp)


@pytest.mark.requirement("FR-age-003")
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


@pytest.mark.requirement("FR-age-001")
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


@pytest.mark.requirement("FR-age-003")
def test_generic_messages_mcp_requires_explicit_admin_env(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_IMESSAGE_ALLOW_GENERIC_MESSAGES_MCP", raising=False)
    args = type("Args", (), {"client": "both", "with_messages": True})()

    with pytest.raises(SystemExit):
        mcp.command_install(args)


@pytest.mark.requirement("FR-age-001")
def test_notify_user_defaults_to_koosha_role(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp, "call_agent_imessage", lambda args: calls.append(args) or {"ok": True})

    assert mcp.tool_call("notify_user", {"message": "hello"}) == {"ok": True}

    assert calls == [["notify", "--recipient", "koosha", "hello"]]


@pytest.mark.requirement("FR-age-003")
def test_notify_user_accepts_only_scoped_recipient_roles(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp, "call_agent_imessage", lambda args: calls.append(args) or {"ok": True})

    assert mcp.tool_call("notify_user", {"recipient": "sponsor", "message": "hello", "dry_run": True}) == {"ok": True}

    assert calls == [["notify", "--recipient", "sponsor", "hello", "--dry-run"]]
    with pytest.raises(ValueError):
        mcp.tool_call("notify_user", {"recipient": "random-contact", "message": "hello"})


@pytest.mark.requirement("FR-AGENT_USER_STATUS-011")
def test_notify_user_structured_forwards_metadata(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp, "call_agent_imessage", lambda args: calls.append(args) or {"ok": True})

    result = mcp.tool_call(
        "notify_user_structured",
        {
            "recipient": "koosha",
            "message": "Need input",
            "project": "agent-user-status",
            "task_id": "FR-011",
            "session_id": "sess-1",
            "correlation_id": "corr-1",
            "dry_run": True,
        },
    )

    assert result == {"ok": True}
    assert calls == [
        [
            "notify-structured",
            "--recipient",
            "koosha",
            "Need input",
            "--session-id",
            "sess-1",
            "--task-id",
            "FR-011",
            "--project",
            "agent-user-status",
            "--correlation-id",
            "corr-1",
            "--dry-run",
        ]
    ]


@pytest.mark.requirement("FR-AGENT_USER_STATUS-013")
def test_parse_user_reply_forwards_schema(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp, "call_agent_imessage", lambda args: calls.append(args) or {"ok": True})
    schema = '{"questions":[{"prompt":"Pick","options":[{"label":"One"}]}]}'

    assert mcp.tool_call("parse_user_reply", {"reply": "A1", "answer_schema_json": schema}) == {"ok": True}

    assert calls == [["parse-reply", "A1", "--answer-schema-json", schema]]


@pytest.mark.requirement("FR-age-001")
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


@pytest.mark.requirement("FR-age-001")
def test_session_tools_are_exposed() -> None:
    names = {tool["name"] for tool in mcp.TOOLS}

    assert {"sessions", "session_heartbeat", "session_event", "session_scan", "session_events"} <= names


@pytest.mark.requirement("FR-age-006")
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


@pytest.mark.requirement("FR-age-006")
def test_session_events_tool_forwards_filters(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(mcp, "call_agent_imessage", lambda args: calls.append(args) or {"ok": True})

    assert mcp.tool_call("session_events", {"session_id": "codex-123", "kind": "event", "limit": 5}) == {"ok": True}

    assert calls == [["session-events", "--limit", "5", "--kind", "event", "--session-id", "codex-123"]]
