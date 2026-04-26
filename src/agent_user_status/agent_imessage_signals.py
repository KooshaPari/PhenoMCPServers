#!/usr/bin/env python3
"""Local activity signal collectors for agent-imessage."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

RunCommand = Callable[[list[str], int], CompletedProcess[str]]
ParseDatetime = Callable[[str | None], datetime | None]
ReadJsonFile = Callable[[Path], dict[str, Any] | None]


def frontmost_app_signal(run_cmd: RunCommand) -> dict[str, Any]:
    result = run_cmd(
        [
            "osascript",
            "-e",
            'tell application "System Events" to get name of first application process whose frontmost is true',
        ],
        timeout=5,
    )
    if result.returncode != 0:
        return {"name": "frontmost_app", "ok": False, "reason": result.stderr.strip()}
    app = result.stdout.strip()
    app_lower = app.lower()
    coding_apps = {
        "terminal",
        "iterm2",
        "warp",
        "ghostty",
        "visual studio code",
        "cursor",
        "zed",
        "xcode",
    }
    focus_apps = {"zoom.us", "zoom", "slack", "notion", "arc", "safari", "google chrome"}
    if app_lower in coding_apps or "code" in app_lower or "terminal" in app_lower:
        score, state = 0.72, "workstation_active"
    elif app_lower in focus_apps:
        score, state = 0.52, "active_elsewhere"
    else:
        score, state = 0.45, "unknown_app"
    return {"name": "frontmost_app", "ok": True, "app": app, "score": score, "state": state}


def process_activity_signal(run_cmd: RunCommand) -> dict[str, Any]:
    result = run_cmd(["ps", "-axo", "comm="], timeout=5)
    if result.returncode != 0:
        return {"name": "process_activity", "ok": False, "reason": result.stderr.strip()}
    names = [Path(line.strip()).name for line in result.stdout.splitlines() if line.strip()]
    lowered = [name.lower() for name in names]

    groups = {
        "agent": ("codex", "claude"),
        "coding": ("ghostty", "terminal", "iterm", "xcode", "cursor", "visual studio code", "code helper", "zed"),
        "comms": ("messages", "slack", "zoom", "facetime"),
        "media": ("spotify", "music", "tv", "quicktime", "vlc", "youtube"),
        "browser": ("safari", "chrome", "edge", "arc", "firefox"),
        "remote": ("parsec", "screensharing", "remotedesktop"),
    }
    hits: dict[str, list[str]] = {}
    for group, needles in groups.items():
        matched = sorted({names[i] for i, value in enumerate(lowered) if any(n in value for n in needles)})
        if matched:
            hits[group] = matched[:8]

    if hits.get("agent") and hits.get("coding"):
        score, state = 0.76, "agent_work_active"
    elif hits.get("coding"):
        score, state = 0.7, "coding_processes_open"
    elif hits.get("comms"):
        score, state = 0.58, "communication_processes_open"
    elif hits.get("remote"):
        score, state = 0.5, "remote_session_open"
    elif hits.get("media"):
        score, state = 0.38, "media_processes_open"
    elif hits.get("browser"):
        score, state = 0.45, "browser_processes_open"
    else:
        score, state = 0.35, "process_context_unknown"
    return {
        "name": "process_activity",
        "ok": True,
        "score": score,
        "state": state,
        "process_groups": hits,
    }


def media_activity_signal(run_cmd: RunCommand) -> dict[str, Any]:
    result = run_cmd(["pmset", "-g", "assertions"], timeout=5)
    if result.returncode != 0:
        return {"name": "media_activity", "ok": False, "reason": result.stderr.strip()}
    text = result.stdout
    audio_active = bool(re.search(r"coreaudiod|audio[- ]?out|PreventUserIdle.*audio", text, re.IGNORECASE))
    display_asserted = "PreventUserIdleDisplaySleep" in text
    videoish = bool(re.search(r"QuickTime|TV|VLC|YouTube|Netflix|Spotify|Edge|Chrome|Safari", text, re.IGNORECASE))

    if audio_active and videoish:
        score, state = 0.3, "video_or_audio_playing"
    elif audio_active:
        score, state = 0.48, "audio_playing"
    elif display_asserted:
        score, state = 0.44, "display_kept_awake"
    else:
        score, state = 0.5, "no_media_assertion"
    return {
        "name": "media_activity",
        "ok": True,
        "score": score,
        "weight": 0.7,
        "state": state,
        "audio_active": audio_active,
        "display_asserted": display_asserted,
    }


def idle_time_signal(run_cmd: RunCommand) -> dict[str, Any]:
    result = run_cmd(["ioreg", "-c", "IOHIDSystem"], timeout=5)
    if result.returncode != 0:
        return {"name": "hid_idle", "ok": False, "reason": result.stderr.strip()}
    match = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', result.stdout)
    if not match:
        return {"name": "hid_idle", "ok": False, "reason": "HIDIdleTime not found"}
    idle_seconds = int(match.group(1)) / 1_000_000_000
    if idle_seconds <= 30:
        score, state = 0.9, "active"
    elif idle_seconds <= 120:
        score, state = 0.72, "recently_active"
    elif idle_seconds <= 600:
        score, state = 0.42, "idle"
    else:
        score, state = 0.12, "away"
    return {
        "name": "hid_idle",
        "ok": True,
        "idle_seconds": round(idle_seconds, 1),
        "score": score,
        "state": state,
    }


def external_signal_records(
    signals_path: Path,
    read_json_file: ReadJsonFile,
    parse_dt: ParseDatetime,
) -> list[dict[str, Any]]:
    data = read_json_file(signals_path)
    if not data:
        return []
    records = data.get("signals", data if isinstance(data, list) else [])
    now = datetime.now(UTC)
    fresh: list[dict[str, Any]] = []
    for record in records if isinstance(records, list) else []:
        if not isinstance(record, dict):
            continue
        observed_at = parse_dt(record.get("observed_at") or record.get("updated_at"))
        max_age = int(record.get("max_age_seconds", 300))
        if not observed_at:
            continue
        if (now - observed_at).total_seconds() > max_age:
            continue
        fresh.append(record)
    return fresh
