from pathlib import Path

import pytest

from agent_user_status.bootstrap_doctor import BOOTSTRAP_HELPER_MODULES
from agent_user_status.bootstrap_support import SUPPORT_MODULES, agent_imessage_bin, imsg_bin, runtime_bin_dir


@pytest.mark.requirement("FR-AGENT_USER_STATUS-001")
def test_runtime_bin_dir_defaults_to_local_bin(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_USER_STATUS_BIN_DIR", raising=False)

    assert runtime_bin_dir() == Path.home() / ".local" / "bin"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_agent_imessage_bin_uses_runtime_bin_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AGENT_IMESSAGE_BIN", raising=False)
    monkeypatch.setenv("AGENT_USER_STATUS_BIN_DIR", str(tmp_path / "bin"))

    assert agent_imessage_bin() == tmp_path / "bin" / "agent-imessage"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_agent_imessage_bin_explicit_override_wins(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_USER_STATUS_BIN_DIR", str(tmp_path / "bin"))
    monkeypatch.setenv("AGENT_IMESSAGE_BIN", str(tmp_path / "custom" / "agent-imessage"))

    assert agent_imessage_bin() == tmp_path / "custom" / "agent-imessage"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_imsg_bin_explicit_override_wins(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_USER_STATUS_BIN_DIR", str(tmp_path / "bin"))
    monkeypatch.setenv("IMSG_BIN", str(tmp_path / "imsg-wrapper"))

    assert imsg_bin() == tmp_path / "imsg-wrapper"


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_support_manifest_includes_decomposed_runtime_modules() -> None:
    support_expected = {
        "agent_imessage_action_learning.py",
        "agent_imessage_comm_commands.py",
        "agent_imessage_elicitation.py",
        "agent_imessage_envelope.py",
        "agent_imessage_mcp_comm.py",
        "agent_imessage_mcp_presence.py",
        "agent_imessage_outbox.py",
        "agent_imessage_presence_commands.py",
        "agent_imessage_signals.py",
        "codex_hooks.py",
        "gaze_projection_types.py",
        "jsonl_tail.py",
        "statusd_eye.py",
    }
    helper_expected = {"bootstrap_doctor.py", "bootstrap_eye_setup.py", "bootstrap_runtime.py"}

    assert support_expected.issubset(set(SUPPORT_MODULES))
    assert helper_expected.issubset(set(BOOTSTRAP_HELPER_MODULES))
