#!/usr/bin/env python3
"""Shared primitives for the local iMessage helper."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_user_status import agent_imessage_signals as _signals
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
    role: str
    phone_e164: str
    phone_digits: str
    email: str
    name: str


RECIPIENT_ROLES = ("koosha", "sponsor")
RECIPIENT_ENV_PREFIXES = {
    "koosha": "AGENT_IMESSAGE",
    "sponsor": "AGENT_IMESSAGE_SPONSOR",
}


def require_recipient_role(role: str | None) -> str:
    normalized = (role or "koosha").strip().lower()
    if normalized not in RECIPIENT_ROLES:
        raise ValueError(f"Unsupported recipient role: {role}. Use one of: {', '.join(RECIPIENT_ROLES)}")
    return normalized


def _recipient_value(values: dict[str, str], role: str, key: str, default: str = "") -> str:
    prefix = RECIPIENT_ENV_PREFIXES[role]
    if role == "koosha":
        return values.get(f"{prefix}_{key}", default)
    return values.get(f"{prefix}_{key}", default)


def load_recipient_config(role: str | None = "koosha") -> Config:
    recipient = require_recipient_role(role)
    values: dict[str, str] = {}
    if CONFIG_PATH.exists():
        for line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip().removeprefix("export ")] = value.strip().strip("\"'")

    phone_default = "+14243305106" if recipient == "koosha" else ""
    phone_e164 = _recipient_value(values, recipient, "PHONE_E164", phone_default)
    digits = re.sub(r"\D", "", phone_e164)
    return Config(
        role=recipient,
        phone_e164=phone_e164,
        phone_digits=_recipient_value(values, recipient, "PHONE_DIGITS", digits[-10:]),
        email=_recipient_value(values, recipient, "EMAIL", "kooshapari@gmail.com" if recipient == "koosha" else ""),
        name=_recipient_value(values, recipient, "NAME", "Koosha" if recipient == "koosha" else "Sponsor"),
    )


def load_config() -> Config:
    return load_recipient_config("koosha")


def recipient_send_address(config: Config) -> str:
    address = config.phone_e164.strip() or config.email.strip()
    if not address:
        raise ValueError(
            f"No contact configured for recipient role '{config.role}'. "
            f"Set {RECIPIENT_ENV_PREFIXES[config.role]}_PHONE_E164 or "
            f"{RECIPIENT_ENV_PREFIXES[config.role]}_EMAIL."
        )
    return address


def run_imsg(args: list[str], timeout: int | None = 30) -> subprocess.CompletedProcess[str]:
    if not IMSG.exists():
        raise SystemExit(f"imsg binary not found at {IMSG}")
    return subprocess.run(
        [str(IMSG), *args],
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def run_cmd(args: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            text=True,
            capture_output=True,
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
        return datetime.fromisoformat(text).astimezone(UTC)
    except ValueError:
        return None


def iso_now() -> str:
    return datetime.now(UTC).isoformat()


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
    return sorted(messages, key=lambda item: message_time(item) or datetime.min.replace(tzinfo=UTC))


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
    if until and until < datetime.now(UTC):
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
    return _signals.frontmost_app_signal(run_cmd)


def process_activity_signal() -> dict[str, Any]:
    return _signals.process_activity_signal(run_cmd)


def media_activity_signal() -> dict[str, Any]:
    return _signals.media_activity_signal(run_cmd)


def idle_time_signal() -> dict[str, Any]:
    return _signals.idle_time_signal(run_cmd)


def external_signal_records() -> list[dict[str, Any]]:
    return _signals.external_signal_records(SIGNALS_PATH, read_json_file, parse_dt)
