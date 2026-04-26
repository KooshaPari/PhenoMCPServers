from __future__ import annotations

from agent_user_status import codex_hooks


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
