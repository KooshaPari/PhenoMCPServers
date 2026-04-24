#!/usr/bin/env python3
"""Privacy-safe JSONL registry for local agent sessions."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_user_status.session_privacy import safe_metadata, safe_text

DEFAULT_TTL_SECONDS = 300
STATE_DIR = Path(os.environ.get("AGENT_IMESSAGE_STATE_DIR", "~/.local/share/agent-imessage/state")).expanduser()
SESSION_LOG_PATH = Path(
    os.environ.get("AGENT_USER_STATUS_SESSION_LOG", STATE_DIR / "agent_sessions.jsonl")
).expanduser()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def record_id(record: Mapping[str, Any]) -> str:
    stable = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def _session_path(store_path: Path | None = None) -> Path:
    return store_path or SESSION_LOG_PATH


def _fresh(record: Mapping[str, Any], now: datetime | None = None) -> bool:
    observed = parse_dt(str(record.get("observed_at") or ""))
    if observed is None:
        return False
    try:
        ttl_seconds = int(record.get("ttl_seconds", DEFAULT_TTL_SECONDS))
    except (TypeError, ValueError):
        ttl_seconds = DEFAULT_TTL_SECONDS
    return ((now or datetime.now(UTC)) - observed).total_seconds() <= ttl_seconds


def append_session_record(record: dict[str, Any], store_path: Path | None = None) -> dict[str, Any]:
    """Append a privacy-checked session record to the JSONL store."""
    path = _session_path(store_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(record)
    payload["record_id"] = record_id({key: value for key, value in payload.items() if key != "record_id"})
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return payload


def append_session_heartbeat(
    session_id: str,
    agent_id: str = "agent",
    status: str = "active",
    *,
    state: str | None = None,
    note: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    observed_at: str | None = None,
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Record a short-lived heartbeat without transcript or screenshot payloads."""
    ttl = int(ttl_seconds)
    if ttl < 1 or ttl > 86_400:
        raise ValueError("ttl_seconds must be between 1 and 86400")
    record: dict[str, Any] = {
        "kind": "heartbeat",
        "observed_at": observed_at or now_iso(),
        "session_id": safe_text(session_id, "session_id", 120),
        "agent_id": safe_text(agent_id, "agent_id", 80),
        "status": safe_text(status, "status", 80),
        "ttl_seconds": ttl,
        "metadata": safe_metadata(metadata),
    }
    if state is not None:
        record["state"] = safe_text(state, "state", 120)
    if note is not None:
        record["note"] = safe_text(note, "note")
    return append_session_record(record, store_path=store_path)


def append_session_event(
    session_id: str,
    event_type: str,
    *,
    agent_id: str = "agent",
    state: str | None = None,
    note: str | None = None,
    metadata: Mapping[str, Any] | None = None,
    observed_at: str | None = None,
    store_path: Path | None = None,
) -> dict[str, Any]:
    """Record an abstract session event such as checkpoint, blocked, or validation."""
    record: dict[str, Any] = {
        "kind": "event",
        "observed_at": observed_at or now_iso(),
        "session_id": safe_text(session_id, "session_id", 120),
        "agent_id": safe_text(agent_id, "agent_id", 80),
        "event_type": safe_text(event_type, "event_type", 80),
        "metadata": safe_metadata(metadata),
    }
    if state is not None:
        record["state"] = safe_text(state, "state", 120)
    if note is not None:
        record["note"] = safe_text(note, "note")
    return append_session_record(record, store_path=store_path)


def recent_session_records(
    *,
    store_path: Path | None = None,
    session_id: str | None = None,
    kind: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Read recent session records, skipping malformed JSONL lines."""
    path = _session_path(store_path)
    if not path.exists():
        return []
    bounded_limit = max(1, min(int(limit), 2000))
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[-bounded_limit:]:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if session_id is not None and record.get("session_id") != session_id:
            continue
        if kind is not None and record.get("kind") != kind:
            continue
        records.append(record)
    return records


def session_timeline(
    session_id: str,
    *,
    store_path: Path | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Return one session's timeline in append order."""
    return recent_session_records(store_path=store_path, session_id=session_id, limit=limit)


def session_summaries(*, store_path: Path | None = None, limit: int = 200) -> list[dict[str, Any]]:
    """Return latest heartbeat and event state for recent sessions."""
    records = recent_session_records(store_path=store_path, limit=limit)
    sessions: dict[str, dict[str, Any]] = {}
    for record in records:
        session_id = str(record.get("session_id") or "")
        if not session_id:
            continue
        summary = sessions.setdefault(
            session_id,
            {"session_id": session_id, "latest": record, "heartbeat": None, "last_event": None},
        )
        summary["latest"] = record
        if record.get("kind") == "heartbeat":
            summary["heartbeat"] = record
        elif record.get("kind") == "event":
            summary["last_event"] = record

    now = datetime.now(UTC)
    output: list[dict[str, Any]] = []
    for summary in sessions.values():
        heartbeat = summary.get("heartbeat")
        summary["fresh"] = bool(isinstance(heartbeat, dict) and _fresh(heartbeat, now=now))
        output.append(summary)
    output.sort(key=lambda item: str(item["latest"].get("observed_at", "")), reverse=True)
    return output
