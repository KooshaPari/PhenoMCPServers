from __future__ import annotations

from argparse import Namespace

from agent_user_status import agent_imessage_core as core
from agent_user_status import agent_imessage_session_commands as commands
from agent_user_status.optional_dependencies import is_imessage_available


def test_session_child_spawn_command_records_structured_event(monkeypatch, capsys) -> None:
    calls = []

    def fake_append(*args, **kwargs):
        calls.append((args, kwargs))
        return {"kind": "event", "event_type": "child_spawn"}

    monkeypatch.setattr(core, "is_imessage_available", lambda: True)
    monkeypatch.setattr(commands, "append_child_session_event", fake_append)

    rc = commands.command_session_child(
        Namespace(
            parent_session_id="parent",
            child_session_id="child",
            lifecycle="spawn",
            agent="manager",
            child_agent="worker-a",
            state="spawned",
            note="lane started",
            result=None,
            pid=None,
            cwd=None,
            repo="agent-user-status",
            tty=None,
            tmux_pane=None,
        )
    )

    assert rc == 0
    assert '"event_type": "child_spawn"' in capsys.readouterr().out
    assert calls == [
        (
            ("parent", "child", "spawn"),
            {
                "agent_id": "manager",
                "child_agent_id": "worker-a",
                "state": "spawned",
                "note": "lane started",
                "metadata": {"repo": "agent-user-status"},
            },
        )
    ]


def test_session_child_command_silently_no_ops_when_imessage_unavailable(monkeypatch, capsys) -> None:
    monkeypatch.setattr(core, "is_imessage_available", lambda: False)
    called = []
    monkeypatch.setattr(
        commands,
        "append_child_session_event",
        lambda *a, **k: called.append((a, k)) or {"kind": "event", "event_type": "child_spawn"},
    )

    rc = commands.command_session_child(
        Namespace(
            parent_session_id="parent",
            child_session_id="child",
            lifecycle="spawn",
            agent="manager",
            child_agent="worker-a",
            state="spawned",
            note="lane started",
            result=None,
            pid=None,
            cwd=None,
            repo="agent-user-status",
            tty=None,
            tmux_pane=None,
        )
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert called == []  # not invoked when imessage is unavailable
    assert '"skipped": "imessage_unavailable"' in out


def test_session_heartbeat_command_silently_no_ops_when_imessage_unavailable(monkeypatch, capsys) -> None:
    monkeypatch.setattr(core, "is_imessage_available", lambda: False)
    called = []
    monkeypatch.setattr(
        commands,
        "append_session_heartbeat",
        lambda *a, **k: called.append((a, k)) or {"ok": True},
    )

    rc = commands.command_session_heartbeat(
        Namespace(
            session_id="sess-1",
            agent="agent",
            status="active",
            state=None,
            note=None,
            pid=None,
            cwd=None,
            repo=None,
            tty=None,
            tmux_pane=None,
            ttl_seconds=300,
        )
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert called == []
    assert '"skipped": "imessage_unavailable"' in out
