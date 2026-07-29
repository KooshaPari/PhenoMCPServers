from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_user_status import agent_imessage_commands as commands
from agent_user_status import agent_imessage_core as core


def write_env(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


# All tests in this module exercise code paths that need to *see* imessage
# available. The optional-dependency guard short-circuits to a uniform
# unavailable payload before any real work, so we patch the probe.
@pytest.fixture(autouse=True)
def _imessage_available(monkeypatch):
    monkeypatch.setattr(core, "is_imessage_available", lambda: True)
    monkeypatch.setattr(core, "is_available", lambda: True)
    monkeypatch.setattr(commands, "is_imessage_available", lambda: True)
    yield


def test_load_config_keeps_koosha_defaults(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(core, "CONFIG_PATH", tmp_path / "missing.env")

    config = core.load_config()

    assert config.role == "koosha"
    assert config.phone_e164 == "+14243305106"
    assert config.phone_digits == "4243305106"
    assert config.email == "kooshapari@gmail.com"
    assert config.name == "Koosha"


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


def test_notify_dry_run_defaults_to_koosha(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr(core, "CONFIG_PATH", tmp_path / "missing.env")
    monkeypatch.setattr(commands, "CONFIG_PATH", tmp_path / "missing.env", raising=False)
    args = commands.build_parser().parse_args(["notify", "hello", "--dry-run"])

    assert commands.command_notify(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["recipient"] == "koosha"
    assert payload["to"] == "+14243305106"
    assert payload["message"] == "hello"


def test_notify_sponsor_requires_configured_contact(monkeypatch, capsys, tmp_path) -> None:
    monkeypatch.setattr(core, "CONFIG_PATH", tmp_path / "missing.env")
    args = commands.build_parser().parse_args(["notify", "--recipient", "sponsor", "hello", "--dry-run"])

    assert commands.command_notify(args) == 2
    assert "No contact configured for recipient role 'sponsor'" in capsys.readouterr().err


def test_wait_uses_recipient_scoped_state_file(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands, "STATE_DIR", tmp_path)
    monkeypatch.setattr(commands, "load_recipient_config", lambda _role: core.Config("sponsor", "", "", "", "Sponsor"))
    monkeypatch.setattr(commands, "recent_messages", lambda _config, _limit: (None, []))
    args = commands.build_parser().parse_args(["wait", "--recipient", "sponsor", "--timeout", "0"])

    assert commands.command_wait(args) == 124
    assert not (tmp_path / "last_seen_message_id").exists()
