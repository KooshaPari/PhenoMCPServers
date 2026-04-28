from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agent_user_status import agent_imessage_comm_commands as comm
from agent_user_status import agent_imessage_commands as commands
from agent_user_status import agent_imessage_core as core
from agent_user_status import agent_imessage_outbox as outbox


def write_env(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_load_config_keeps_koosha_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(core, "CONFIG_PATH", tmp_path / "missing.env")

    config = core.load_config()

    assert config.role == "koosha"
    assert config.phone_e164 == "+14243305106"
    assert config.phone_digits == "4243305106"
    assert config.email == "kooshapari@gmail.com"
    assert config.name == "Koosha"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_load_recipient_config_reads_scoped_sponsor_values(monkeypatch, tmp_path) -> None:
    env_path = tmp_path / "agent-imessage.env"
    write_env(
        env_path,
        "\n".join(
            [
                "AGENT_IMESSAGE_PHONE_E164=+15550000000",
                "AGENT_IMESSAGE_SPONSOR_PHONE_E164=+15551112222",
                "AGENT_IMESSAGE_SPONSOR_EMAIL=sponsor@example.com",
                "AGENT_IMESSAGE_SPONSOR_NAME=Project Sponsor",
            ]
        ),
    )
    monkeypatch.setattr(core, "CONFIG_PATH", env_path)

    sponsor = core.load_recipient_config("sponsor")
    koosha = core.load_recipient_config("koosha")

    assert sponsor.role == "sponsor"
    assert sponsor.phone_e164 == "+15551112222"
    assert sponsor.phone_digits == "5551112222"
    assert sponsor.email == "sponsor@example.com"
    assert sponsor.name == "Project Sponsor"
    assert koosha.phone_e164 == "+15550000000"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-001")
def test_notify_dry_run_defaults_to_koosha(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr(core, "CONFIG_PATH", tmp_path / "missing.env")
    monkeypatch.setattr(commands, "CONFIG_PATH", tmp_path / "missing.env", raising=False)
    args = commands.build_parser().parse_args(["notify", "hello", "--dry-run"])

    assert commands.command_notify(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["recipient"] == "koosha"
    assert payload["to"] == "+14243305106"
    assert payload["message"] == "hello"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-011")
@pytest.mark.requirement("FR-AGENT_USER_STATUS-013")
def test_notify_structured_dry_run_renders_envelope(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr(core, "CONFIG_PATH", tmp_path / "missing.env")
    schema = json.dumps({"questions": [{"prompt": "Proceed?", "options": [{"label": "Yes"}, {"label": "No"}]}]})
    args = commands.build_parser().parse_args(
        [
            "notify-structured",
            "Need approval.",
            "--project",
            "agent-user-status",
            "--task-id",
            "FR-011",
            "--session-id",
            "sess-1",
            "--correlation-id",
            "corr-1",
            "--answer-schema-json",
            schema,
            "--dry-run",
        ]
    )

    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["recipient"] == "koosha"
    assert payload["envelope"]["correlation_id"] == "corr-1"
    assert "Project: agent-user-status" in payload["rendered_message"]
    assert "A2: No" in payload["rendered_message"]


@pytest.mark.requirement("FR-AGENT_USER_STATUS-001")
def test_notify_sponsor_requires_configured_contact(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr(core, "CONFIG_PATH", tmp_path / "missing.env")
    args = commands.build_parser().parse_args(["notify", "--recipient", "sponsor", "hello", "--dry-run"])

    assert commands.command_notify(args) == 2
    assert "No contact configured for recipient role 'sponsor'" in capsys.readouterr().err


@pytest.mark.requirement("FR-AGENT_USER_STATUS-014")
def test_wait_uses_recipient_scoped_state_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands, "STATE_DIR", tmp_path)
    monkeypatch.setattr(commands, "load_recipient_config", lambda _role: core.Config("sponsor", "", "", "", "Sponsor"))
    monkeypatch.setattr(commands, "recent_messages", lambda _config, _limit: (None, []))
    args = commands.build_parser().parse_args(["wait", "--recipient", "sponsor", "--timeout", "0"])

    assert commands.command_wait(args) == 124
    assert not (tmp_path / "last_seen_message_id").exists()


@pytest.mark.requirement("FR-AGENT_USER_STATUS-013")
def test_parse_reply_command_outputs_structured_selection(capsys) -> None:
    schema = json.dumps(
        {
            "questions": [
                {
                    "prompt": "Pick targets",
                    "kind": "multi_answer",
                    "options": [{"label": "One"}, {"label": "Two"}, {"label": "Three"}],
                }
            ]
        }
    )
    args = commands.build_parser().parse_args(["parse-reply", "A1 A3 please", "--answer-schema-json", schema])

    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["selected_answer_ids"] == ["A1", "A3"]
    assert payload["freeform_text"] == "please"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-014")
def test_wait_records_response_correlation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands, "STATE_DIR", tmp_path)
    monkeypatch.setattr(commands, "load_recipient_config", lambda _role: core.Config("koosha", "", "", "", "Koosha"))
    monkeypatch.setattr(commands, "recent_messages", lambda _config, _limit: (None, [{"id": "reply-1", "text": "A1"}]))
    monkeypatch.setattr(commands, "inbound_messages", lambda _config, messages: messages)
    monkeypatch.setattr(
        commands,
        "latest_outbox_state",
        lambda **kwargs: {"message_id": "msg-1", "correlation_id": "corr-1", "recipient": "koosha"},
    )
    captured: list[dict[str, object]] = []
    monkeypatch.setattr(commands, "record_response_received", lambda **kwargs: captured.append(kwargs) or {"ok": True})

    args = commands.build_parser().parse_args(["wait", "--include-existing", "--timeout", "1"])

    assert commands.command_wait(args) == 0
    assert captured == [
        {
            "message_id": "msg-1",
            "correlation_id": "corr-1",
            "recipient": "koosha",
            "response_id": "reply-1",
            "response_body": "A1",
            "note": "inbound reply observed",
        }
    ]


@pytest.mark.requirement("FR-AGENT_USER_STATUS-012")
def test_echo_delete_uses_configured_cleanup_command(monkeypatch, capsys) -> None:
    monkeypatch.setenv(
        "AGENT_IMESSAGE_ECHO_DELETE_CMD",
        "echo delete {message_id} {correlation_id} {recipient}",
    )
    monkeypatch.setattr(
        comm,
        "latest_outbox_state",
        lambda **kwargs: {
            "message_id": "msg-1",
            "correlation_id": "corr-1",
            "recipient": "koosha",
            "project": "agent-user-status",
            "task_id": "FR-012",
        },
    )
    monkeypatch.setattr(outbox, "append_outbox_record", lambda record, store_path=None: record.to_dict())
    monkeypatch.setattr(comm, "run_cmd", lambda args, timeout=30: subprocess.CompletedProcess(args, 0))

    args = commands.build_parser().parse_args(["echo-delete", "--message-id", "msg-1"])

    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["echo_cleanup"]["echo_state"] == "deleted"
