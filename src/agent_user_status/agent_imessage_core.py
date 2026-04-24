#!/usr/bin/env python3
"""Shared primitives for the local iMessage helper."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_user_status.bootstrap_support import imsg_bin

CONFIG_PATH = Path(os.environ.get("AGENT_IMESSAGE_ENV", "~/.config/phenotype/agent-imessage.env")).expanduser()
STATE_DIR = Path(os.environ.get("AGENT_IMESSAGE_STATE_DIR", "~/.local/share/agent-imessage/state")).expanduser()
IMSG = imsg_bin()
OVERRIDE_PATH = STATE_DIR / "presence_override.json"
SIGNALS_PATH = STATE_DIR / "signals.json"
ACTION_LOG_PATH = STATE_DIR / "action_events.jsonl"
RESPONSE_LOG_PATH = STATE_DIR / "response_events.jsonl"
LEARNING_PATH = STATE_DIR / "learning.json"
ACTION_LEARNING_PATH = STATE_DIR / "action_learning.json"

WAITING_PATTERNS = re.compile(
    r"\b(waiting|let me know|confirm|which option|do you want|should i|would you like|"
    r"can you|please send|reply|your response|your answer|need your input)\b",
    re.IGNORECASE,
)

RAW_SENSOR_PATTERNS = re.compile(
    r"(^|[^a-z0-9])(raw|frame|image|photo|screenshot|face|facial|biometric|"
    r"pupil|retina|iris|embedding|landmark|camera|webcam)($|[^a-z0-9])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Config:
    phone_e164: str
    phone_digits: str
    email: str
    name: str


def load_config() -> Config:
    values: dict[str, str] = {}
    if CONFIG_PATH.exists():
        for line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip().removeprefix("export ")] = value.strip().strip("\"'")

    phone_e164 = values.get("AGENT_IMESSAGE_PHONE_E164", "+14243305106")
    digits = re.sub(r"\D", "", phone_e164)
    return Config(
        phone_e164=phone_e164,
        phone_digits=values.get("AGENT_IMESSAGE_PHONE_DIGITS", digits[-10:]),
        email=values.get("AGENT_IMESSAGE_EMAIL", "kooshapari@gmail.com"),
        name=values.get("AGENT_IMESSAGE_NAME", "Koosha"),
    )


def run_imsg(args: list[str], timeout: int | None = 30) -> subprocess.CompletedProcess[str]:
    if not IMSG.exists():
        raise SystemExit(f"imsg binary not found at {IMSG}")
    return subprocess.run(
        [str(IMSG), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def run_cmd(args: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        return subprocess.CompletedProcess(
            args=args,
            returncode=124,
            stdout=stdout,
            stderr=f"timed out after {timeout}s",
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(
            args=args,
            returncode=127,
            stdout="",
            stderr=str(exc),
        )


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).astimezone(timezone.utc)
    except ValueError:
        return None


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def validate_abstract_payload(*values: str | None) -> None:
    text = " ".join(value or "" for value in values)
    if RAW_SENSOR_PATTERNS.search(text):
        raise ValueError(
            "Refusing raw sensor/biometric payload. Publish only derived state, score, "
            "screen zone, and short-lived confidence."
        )


def eta_label(minutes: int | None) -> str:
    if minutes is None:
        return "unknown"
    if minutes <= 2:
        return "0-2 min"
    if minutes <= 10:
        return "2-10 min"
    if minutes <= 30:
        return "10-30 min"
    return "30+ min"


def recommendation_for(confidence: float, status: str) -> str:
    if confidence >= 0.7:
        return "wait_briefly"
    if confidence <= 0.3 or status in {"away", "focus", "sleep", "async", "away_or_async"}:
        return "default_or_defer"
    return "use_judgment"


def normalize_sender(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\D", "", value)


def message_time(message: dict[str, Any]) -> datetime | None:
    return parse_dt(message.get("created_at"))


def sort_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(messages, key=lambda item: message_time(item) or datetime.min.replace(tzinfo=timezone.utc))


def inbound_messages(config: Config, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _ = config
    return [message for message in messages if not bool(message.get("is_from_me"))]


def find_user_chat(config: Config) -> dict[str, Any] | None:
    result = run_imsg(["chats", "--limit", "80", "--json"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    phone_tail = config.phone_digits[-10:]
    email = config.email.lower()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        chat = json.loads(line)
        haystack = " ".join(str(chat.get(k, "")) for k in ("name", "identifier", "service")).lower()
        digits = normalize_sender(haystack)
        if phone_tail and phone_tail in digits:
            return chat
        if email and email in haystack:
            return chat
    return None


def recent_messages(config: Config, limit: int) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    chat = find_user_chat(config)
    if not chat:
        return None, []

    result = run_imsg(["history", "--chat-id", str(chat["id"]), "--limit", str(limit), "--json"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    messages: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if line.strip():
            messages.append(json.loads(line))
    return chat, sort_messages(messages)


def read_presence_override() -> dict[str, Any] | None:
    if not OVERRIDE_PATH.exists():
        return None
    try:
        override = json.loads(OVERRIDE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    until = parse_dt(override.get("until"))
    if until and until < datetime.now(timezone.utc):
        return None
    return override


def read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_json_file(path: Path, value: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def frontmost_app_signal() -> dict[str, Any]:
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


def process_activity_signal() -> dict[str, Any]:
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


def media_activity_signal() -> dict[str, Any]:
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


def idle_time_signal() -> dict[str, Any]:
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


def external_signal_records() -> list[dict[str, Any]]:
    data = read_json_file(SIGNALS_PATH)
    if not data:
        return []
    records = data.get("signals", data if isinstance(data, list) else [])
    now = datetime.now(timezone.utc)
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
