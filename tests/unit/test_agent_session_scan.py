from __future__ import annotations

from agent_user_status.session_scan import parse_ps_output, parse_tmux_panes, path_summary


def test_parse_ps_output_keeps_agent_processes_without_args() -> None:
    output = """
      10     1    10 ??       /usr/local/bin/codex
      11     1    11 ??       /bin/launchd
      12    10    10 ttys001  /opt/homebrew/bin/claude
      13     1    13 ??       /Users/me/Agent User Status.app/Contents/MacOS/AgentUserStatusMonitor
    """

    records = parse_ps_output(output)

    assert [record["process"] for record in records] == ["codex", "claude", "AgentUserStatusMonitor"]
    assert records[0]["pid"] == 10
    assert all("args" not in record for record in records)


def test_parse_tmux_panes_redacts_full_cwd_by_default(tmp_path) -> None:
    repo = tmp_path / "agent-user-status"
    repo.mkdir()
    (repo / ".git").mkdir()
    output = f"work\t1\t2\t123\t{repo}\n"

    panes = parse_tmux_panes(output)

    assert panes == [
        {
            "tmux_session": "work",
            "tmux_window": "1",
            "tmux_pane": "2",
            "pane_pid": 123,
            "cwd_basename": "agent-user-status",
            "repo": "agent-user-status",
        }
    ]


def test_path_summary_includes_cwd_only_when_requested(tmp_path) -> None:
    summary = path_summary(str(tmp_path / "repo"), include_cwd=False)
    debug_summary = path_summary(str(tmp_path / "repo"), include_cwd=True)

    assert "cwd" not in summary
    assert debug_summary["cwd"].endswith("/repo")
