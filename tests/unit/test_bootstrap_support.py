from pathlib import Path

from agent_user_status.bootstrap_support import agent_imessage_bin, imsg_bin, runtime_bin_dir


@pytest.mark.requirement("FR-age-001")
def test_runtime_bin_dir_defaults_to_local_bin(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_USER_STATUS_BIN_DIR", raising=False)

    assert runtime_bin_dir() == Path.home() / ".local" / "bin"


@pytest.mark.requirement("FR-age-002")
def test_agent_imessage_bin_uses_runtime_bin_dir(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AGENT_IMESSAGE_BIN", raising=False)
    monkeypatch.setenv("AGENT_USER_STATUS_BIN_DIR", str(tmp_path / "bin"))

    assert agent_imessage_bin() == tmp_path / "bin" / "agent-imessage"


@pytest.mark.requirement("FR-age-002")
def test_agent_imessage_bin_explicit_override_wins(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_USER_STATUS_BIN_DIR", str(tmp_path / "bin"))
    monkeypatch.setenv("AGENT_IMESSAGE_BIN", str(tmp_path / "custom" / "agent-imessage"))

    assert agent_imessage_bin() == tmp_path / "custom" / "agent-imessage"


@pytest.mark.requirement("FR-age-002")
def test_imsg_bin_explicit_override_wins(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AGENT_USER_STATUS_BIN_DIR", str(tmp_path / "bin"))
    monkeypatch.setenv("IMSG_BIN", str(tmp_path / "imsg-wrapper"))

    assert imsg_bin() == tmp_path / "imsg-wrapper"
