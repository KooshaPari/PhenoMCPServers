from __future__ import annotations

import json
import os
import re
import time
from argparse import Namespace

from agent_user_status import agent_imessage_core as core
from agent_user_status import agent_imessage_state_commands
from agent_user_status.state_retention import delete_state, export_state, retain_recent_state


def test_export_state_reads_only_derived_json_and_jsonl(tmp_path) -> None:
    (tmp_path / "signals.json").write_text('{"signals":[{"name":"eye_tracking"}]}', encoding="utf-8")
    (tmp_path / "action_events.jsonl").write_text('{"kind":"mouse_click"}\nnot-json\n', encoding="utf-8")
    (tmp_path / "face_landmarker.task").write_text("model", encoding="utf-8")

    payload = export_state(tmp_path)

    assert sorted(payload["files"]) == ["action_events.jsonl", "signals.json"]
    assert payload["files"]["signals.json"]["payload"]["signals"][0]["name"] == "eye_tracking"
    assert payload["files"]["action_events.jsonl"]["records"] == [
        {"kind": "mouse_click"},
        {"malformed": True},
    ]


def test_delete_state_deletes_only_selected_derived_files(tmp_path) -> None:
    signals = tmp_path / "signals.json"
    events = tmp_path / "action_events.jsonl"
    native = tmp_path / "face_landmarker.task"
    signals.write_text("{}", encoding="utf-8")
    events.write_text("{}\n", encoding="utf-8")
    native.write_text("model", encoding="utf-8")

    result = delete_state(tmp_path, names=["signals.json", "missing.json"])

    assert result == {"deleted": ["signals.json"], "missing": ["missing.json"]}
    assert not signals.exists()
    assert events.exists()
    assert native.exists()


def test_retain_recent_state_removes_old_derived_files(tmp_path) -> None:
    old_file = tmp_path / "old.json"
    fresh_file = tmp_path / "fresh.jsonl"
    old_file.write_text("{}", encoding="utf-8")
    fresh_file.write_text("{}\n", encoding="utf-8")
    old_mtime = time.time() - 120
    os.utime(old_file, (old_mtime, old_mtime))

    result = retain_recent_state(tmp_path, max_age_seconds=60)

    assert result["deleted"] == ["old.json"]
    assert result["kept"] == ["fresh.jsonl"]
    assert not old_file.exists()
    assert fresh_file.exists()


def test_state_export_cli_uses_configured_state_dir(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(core, "is_imessage_available", lambda: True)
    monkeypatch.setattr(agent_imessage_state_commands, "STATE_DIR", tmp_path)
    (tmp_path / "signals.json").write_text('{"signals":[]}', encoding="utf-8")

    assert agent_imessage_state_commands.command_state_export(Namespace()) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["ok"] is True
    assert list(output["export"]["files"]) == ["signals.json"]


def test_state_commands_silently_no_op_when_imessage_unavailable(tmp_path, monkeypatch, capsys) -> None:
    """All state-* subcommands must exit 0 and emit a uniform skipped payload when
    imessage is disabled — never raise or modify the state directory."""
    monkeypatch.setattr(core, "is_imessage_available", lambda: False)
    monkeypatch.setattr(agent_imessage_state_commands, "STATE_DIR", tmp_path)
    (tmp_path / "signals.json").write_text('{"signals":[]}', encoding="utf-8")
    snapshot_calls = []
    monkeypatch.setattr(
        agent_imessage_state_commands,
        "delete_state",
        lambda *_a, **_k: snapshot_calls.append("delete") or {"deleted": [], "missing": []},
    )
    monkeypatch.setattr(
        agent_imessage_state_commands,
        "retain_recent_state",
        lambda *_a, **_k: snapshot_calls.append("retain") or {"deleted": [], "kept": []},
    )
    monkeypatch.setattr(
        agent_imessage_state_commands,
        "export_state",
        lambda *_a, **_k: snapshot_calls.append("export") or {"files": {}},
    )

    rc_export = agent_imessage_state_commands.command_state_export(Namespace())
    rc_delete = agent_imessage_state_commands.command_state_delete(Namespace(name=None))
    rc_retain = agent_imessage_state_commands.command_state_retain(Namespace(max_age_seconds=60))

    captured = capsys.readouterr().out
    assert rc_export == rc_delete == rc_retain == 0
    assert snapshot_calls == []  # never invoked when imessage is unavailable
    assert (tmp_path / "signals.json").exists()  # never deleted
    # Each command pretty-prints its own JSON object; split on the closing
    # brace+newline and re-parse each block.
    payloads = []
    for block in re.findall(r"\{[^{}]*\}", captured, re.DOTALL):
        payloads.append(json.loads(block))
    assert len(payloads) == 3
    for payload in payloads:
        assert payload == {"ok": True, "skipped": "imessage_unavailable"}
