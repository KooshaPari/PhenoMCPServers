from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_user_status import codex_hooks


@pytest.mark.requirement("FR-AGENT_USER_STATUS-015")
def test_codex_hook_records_session_start(monkeypatch) -> None:
    heartbeats = []
    monkeypatch.setattr(
        codex_hooks,
        "append_session_heartbeat",
        lambda *args, **kwargs: heartbeats.append((args, kwargs)),
    )

    result = codex_hooks.handle_codex_hook(
        {
            "hook_event_name": "SessionStart",
            "session_id": "codex-123",
            "cwd": "/tmp/repo",
            "model": "gpt-5.3-codex",
            "source": "startup",
        }
    )

    assert result == {"continue": True}
    assert heartbeats
    assert heartbeats[0][0][0] == "codex-123"
    assert heartbeats[0][1]["metadata"]["session_log_available"] is False


@pytest.mark.requirement("FR-AGENT_USER_STATUS-015")
def test_codex_stop_hook_continues_when_hook_decision_prompts(monkeypatch) -> None:
    events = []
    monkeypatch.setattr(codex_hooks, "append_session_event", lambda *args, **kwargs: events.append((args, kwargs)))
    monkeypatch.setattr(
        codex_hooks,
        "hook_decision_result",
        lambda _text: {"decision": "reprompt_default_or_defer", "prompt": "Continue with the safe default."},
    )

    result = codex_hooks.handle_codex_hook(
        {
            "hook_event_name": "Stop",
            "session_id": "codex-123",
            "turn_id": "turn-1",
            "last_assistant_message": "Waiting for your response.",
            "stop_hook_active": False,
        }
    )

    assert result["decision"] == "block"
    assert result["reason"] == "Continue with the safe default."
    assert events


@pytest.mark.requirement("FR-AGENT_USER_STATUS-015")
def test_codex_stop_hook_allows_when_already_active(monkeypatch) -> None:
    monkeypatch.setattr(codex_hooks, "append_session_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(codex_hooks, "hook_decision_result", lambda _text: {"decision": "reprompt_wait", "prompt": "x"})

    result = codex_hooks.handle_codex_hook(
        {
            "hook_event_name": "Stop",
            "session_id": "codex-123",
            "last_assistant_message": "Waiting for your response.",
            "stop_hook_active": True,
        }
    )

    assert result["continue"] is True
    assert "decision" not in result


@pytest.mark.requirement("FR-AGENT_USER_STATUS-015")
def test_codex_hooks_json_includes_current_events() -> None:
    hooks_path = Path(__file__).resolve().parents[2] / ".codex" / "hooks.json"
    config_path = Path(__file__).resolve().parents[2] / ".codex" / "config.toml"

    config = config_path.read_text(encoding="utf-8")
    payload = json.loads(hooks_path.read_text(encoding="utf-8"))

    assert "codex_hooks = true" in config
    assert {"SessionStart", "PreToolUse", "PermissionRequest", "PostToolUse", "UserPromptSubmit", "Stop"}.issubset(
        set(payload["hooks"])
    )
    assert payload["hooks"]["SessionStart"][0]["matcher"] == "startup|resume|clear"
    assert payload["hooks"]["Stop"][0]["hooks"][0]["timeout"] >= 10


@pytest.mark.requirement("FR-AGENT_USER_STATUS-015")
def test_codex_permission_request_records_without_unsupported_continue(monkeypatch) -> None:
    events = []
    monkeypatch.setattr(codex_hooks, "append_session_event", lambda *args, **kwargs: events.append((args, kwargs)))

    result = codex_hooks.handle_codex_hook(
        {
            "hook_event_name": "PermissionRequest",
            "session_id": "codex-123",
            "tool_name": "Bash",
            "tool_input": {"command": "cat private.txt"},
            "transcript_path": "/tmp/transcript.jsonl",
            "last_assistant_message": "raw assistant text",
        }
    )

    assert result == {}
    metadata = events[0][1]["metadata"]
    assert metadata["tool_name"] == "Bash"
    assert metadata["session_log_available"] is True
    encoded_metadata = json.dumps(metadata)
    assert "private.txt" not in encoded_metadata
    assert "raw assistant text" not in encoded_metadata
    assert "transcript.jsonl" not in encoded_metadata
