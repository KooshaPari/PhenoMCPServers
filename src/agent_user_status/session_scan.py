#!/usr/bin/env python3
"""Privacy-safe local process and tmux session discovery."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

AGENT_PROCESS_TOKENS = ("codex", "claude", "agent-user-status", "agent-imessage", "tmux")


def path_summary(path: str | None, *, include_cwd: bool = False) -> dict[str, Any]:
    if not path:
        return {}
    resolved = Path(path).expanduser()
    output: dict[str, Any] = {"cwd_basename": resolved.name}
    repo = repo_name(resolved)
    if repo:
        output["repo"] = repo
    if include_cwd:
        output["cwd"] = str(resolved)
    return output


def repo_name(path: Path) -> str | None:
    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return candidate.name
    return None


def parse_ps_output(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        parts = line.strip().split(None, 4)
        if len(parts) != 5:
            continue
        pid, ppid, pgid, tty, command = parts
        process = Path(command).name
        if not is_agent_process(process):
            continue
        records.append(
            {
                "pid": int(pid),
                "ppid": int(ppid),
                "pgid": int(pgid),
                "tty": tty,
                "process": process,
            }
        )
    return records


def is_agent_process(process: str) -> bool:
    lowered = process.lower()
    return any(token in lowered for token in AGENT_PROCESS_TOKENS)


def scan_processes() -> list[dict[str, Any]]:
    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,pgid=,tty=,comm="],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return parse_ps_output(result.stdout)


def parse_tmux_panes(text: str, *, include_cwd: bool = False) -> list[dict[str, Any]]:
    panes: list[dict[str, Any]] = []
    for line in text.splitlines():
        session, window, pane, pid, cwd = (line.split("\t", 4) + ["", "", "", "", ""])[:5]
        if not session or not pid:
            continue
        panes.append(
            {
                "tmux_session": session[:80],
                "tmux_window": window[:20],
                "tmux_pane": pane[:20],
                "pane_pid": int(pid),
                **path_summary(cwd, include_cwd=include_cwd),
            }
        )
    return panes


def scan_tmux(*, include_cwd: bool = False) -> list[dict[str, Any]]:
    if not os.environ.get("TMUX") and not shutil.which("tmux"):
        return []
    result = subprocess.run(
        ["tmux", "list-panes", "-a", "-F", "#{session_name}\t#{window_index}\t#{pane_index}\t#{pane_pid}\t#{pane_current_path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return parse_tmux_panes(result.stdout, include_cwd=include_cwd)


def scan_agent_sessions(*, include_cwd: bool = False) -> dict[str, Any]:
    return {
        "processes": scan_processes(),
        "tmux_panes": scan_tmux(include_cwd=include_cwd),
        "privacy": {
            "raw_args": False,
            "raw_transcripts": False,
            "cwd_included": include_cwd,
        },
    }
