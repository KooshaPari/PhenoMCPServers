"""Tests for the ``read-receipts`` and ``user-responses`` poll subcommands.

These subcommands drain the BlueBubbles webhook sink via
``drain_inbound``. They MUST print ``[]`` (not error or non-zero exit)
when imessage is unavailable, because the rust stop-hook and CC/Codex
hooks depend on a uniform no-op shape.
"""

from __future__ import annotations

import json
from argparse import Namespace

import pytest

from agent_user_status import agent_imessage_commands as commands


def test_read_receipts_prints_empty_list_when_imessage_unavailable(monkeypatch, capsys) -> None:
    monkeypatch.setattr(commands, "drain_inbound", lambda *_a, **_k: [])

    rc = commands.command_read_receipts(Namespace(since=None))

    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out) == []


def test_user_responses_prints_empty_list_when_imessage_unavailable(monkeypatch, capsys) -> None:
    monkeypatch.setattr(commands, "drain_inbound", lambda *_a, **_k: [])

    rc = commands.command_user_responses(Namespace(since=None))

    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out) == []


def test_read_receipts_forwards_since_and_kinds(monkeypatch, capsys) -> None:
    captured: list[tuple] = []

    def fake_drain(since_iso, *, kinds):
        captured.append((since_iso, kinds))
        return [{"type": "read_receipt", "received_at": "2026-06-08T00:00:00Z"}]

    monkeypatch.setattr(commands, "drain_inbound", fake_drain)

    rc = commands.command_read_receipts(Namespace(since="2026-06-08T00:00:00Z"))

    out = capsys.readouterr().out
    assert rc == 0
    assert captured == [("2026-06-08T00:00:00Z", ("read_receipt",))]
    assert json.loads(out) == [
        {"type": "read_receipt", "received_at": "2026-06-08T00:00:00Z"}
    ]


def test_user_responses_forwards_since_and_kinds(monkeypatch, capsys) -> None:
    captured: list[tuple] = []

    def fake_drain(since_iso, *, kinds):
        captured.append((since_iso, kinds))
        return [{"type": "reply", "text": "ack"}]

    monkeypatch.setattr(commands, "drain_inbound", fake_drain)

    rc = commands.command_user_responses(Namespace(since="2026-06-08T00:00:00Z"))

    out = capsys.readouterr().out
    assert rc == 0
    assert captured == [("2026-06-08T00:00:00Z", ("reply", "tapback"))]
    assert json.loads(out) == [{"type": "reply", "text": "ack"}]


def test_hook_decision_returns_permissive_when_imessage_unavailable(monkeypatch, capsys) -> None:
    """The rust stop-hook unblocks immediately when imessage is disabled."""
    monkeypatch.setattr(commands, "is_imessage_available", lambda: False)

    rc = commands.command_hook_decision(Namespace(text="waiting for Koosha"))

    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert payload == {
        "ok": True,
        "decision": "allow",
        "reason": "imessage_disabled",
    }


def test_build_parser_exposes_poll_subcommands() -> None:
    parser = commands.build_parser()
    parsed = parser.parse_args(["read-receipts"])
    assert parsed.command == "read-receipts"
    assert parsed.func is commands.command_read_receipts

    parsed = parser.parse_args(["user-responses", "--since", "2026-06-08T00:00:00Z"])
    assert parsed.command == "user-responses"
    assert parsed.since == "2026-06-08T00:00:00Z"
    assert parsed.func is commands.command_user_responses
