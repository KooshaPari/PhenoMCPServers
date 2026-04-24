from __future__ import annotations

from agent_user_status import statusd_sessions


def test_session_snapshot_endpoint_builds_privacy_safe_payload(monkeypatch) -> None:
    calls = []

    def fake_snapshot(**kwargs):
        calls.append(kwargs)
        return {"generated_at": "now", "sessions": [], "events": [], "timeline": []}

    monkeypatch.setattr(statusd_sessions, "session_snapshot", fake_snapshot)

    payload = statusd_sessions.session_get_payload(
        "/session/snapshot",
        {
            "session_id": ["codex-123"],
            "session_limit": ["12"],
            "event_limit": ["8"],
            "kind": ["event"],
        },
    )

    assert payload == {
        "ok": True,
        "snapshot": {"generated_at": "now", "sessions": [], "events": [], "timeline": []},
    }
    assert calls == [
        {
            "session_id": "codex-123",
            "session_limit": 12,
            "event_limit": 8,
            "kind": "event",
        }
    ]


def test_session_event_endpoint_accepts_session_filter(monkeypatch) -> None:
    calls = []

    def fake_events(**kwargs):
        calls.append(kwargs)
        return [{"session_id": "codex-123", "kind": "event"}]

    monkeypatch.setattr(statusd_sessions, "recent_session_events", fake_events)

    payload = statusd_sessions.session_get_payload(
        "/session/events",
        {"session_id": ["codex-123"], "limit": ["5"], "kind": ["event"]},
    )

    assert payload == {"ok": True, "events": [{"session_id": "codex-123", "kind": "event"}]}
    assert calls == [{"limit": 5, "kind": "event", "session_id": "codex-123"}]
