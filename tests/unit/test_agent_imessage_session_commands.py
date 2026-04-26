from __future__ import annotations

from argparse import Namespace

import pytest

from agent_user_status import agent_imessage_session_commands as commands


@pytest.mark.requirement("FR-AGENT_USER_STATUS-001")
@pytest.mark.requirement("FR-AGENT_USER_STATUS-005")
def test_session_child_spawn_command_records_structured_event(monkeypatch, capsys) -> None:
    calls = []

    def fake_append(*args, **kwargs):
        calls.append((args, kwargs))
        return {"kind": "event", "event_type": "child_spawn"}

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
