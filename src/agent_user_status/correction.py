#!/usr/bin/env python3
"""Privacy-preserving correction-grade event storage."""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent_user_status.gaze_context import annotate_event_with_gaze, is_gaze_reliable_event
from agent_user_status.gaze_drift_correction import persist_drift_correction
from agent_user_status.agent_imessage_learning import action_environment_context

STATE_DIR = Path(os.environ.get("AGENT_IMESSAGE_STATE_DIR", "~/.local/share/agent-imessage/state")).expanduser()
CORRECTION_EVENTS_PATH = STATE_DIR / "correction_events.jsonl"


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("numeric value must be finite")
    return parsed


def as_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    return int(value)


def bounded_float(value: Any, default: float, low: float, high: float, name: str) -> float:
    parsed = as_float(value, default)
    if parsed is None or parsed < low or parsed > high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return parsed


def bounded_int(value: Any, default: int, low: int, high: int, name: str) -> int:
    parsed = as_int(value, default)
    if parsed is None or parsed < low or parsed > high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return parsed


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def screen_coord(payload: dict[str, Any]) -> dict[str, float]:
    width = bounded_float(payload.get("screen_width"), 0.0, 1.0, 100000.0, "screen_width")
    height = bounded_float(payload.get("screen_height"), 0.0, 1.0, 100000.0, "screen_height")
    x = bounded_float(payload.get("screen_x"), 0.0, 0.0, width, "screen_x")
    y = bounded_float(payload.get("screen_y"), 0.0, 0.0, height, "screen_y")
    return {"screen_x": x, "screen_y": y, "screen_width": width, "screen_height": height}


def store_correction_event(payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("kind", ""))
    allowed_kinds = {
        "audio_activity",
        "cursor_click",
        "cursor_target",
        "explicit_alignment",
        "keyboard_activity",
    }
    if kind not in allowed_kinds:
        raise ValueError(f"kind must be one of {', '.join(sorted(allowed_kinds))}")

    event: dict[str, Any] = {
        "observed_at": now_iso(),
        "kind": kind,
        "score": bounded_float(payload.get("score"), 0.5, 0.0, 1.0, "score"),
        "max_age_seconds": bounded_int(payload.get("max_age_seconds"), 30, 1, 3600, "max_age_seconds"),
        "state": str(payload.get("state") or kind)[:120],
        "harmony_hint": bool(payload.get("harmony_hint", False)),
    }
    if kind in {"cursor_click", "cursor_target", "explicit_alignment"}:
        event.update(screen_coord(payload))
    if payload.get("window_owner"):
        event["window_owner"] = str(payload["window_owner"])[:120]
    if payload.get("window_role"):
        event["window_role"] = str(payload["window_role"])[:80]
    if payload.get("input_modality"):
        event["input_modality"] = str(payload["input_modality"])[:40]
    annotate_event_with_gaze(event)
    context = action_environment_context()
    if not event.get("window_role") and context.get("window_role"):
        event["window_role"] = str(context["window_role"])[:80]
    if not event.get("window_owner") and context.get("frontmost_app"):
        event["window_owner"] = str(context["frontmost_app"])[:120]
    event["learnable"] = bool(event.get("gaze_targeting_reliable", True) and event.get("gaze_fresh", True))
    append_jsonl(CORRECTION_EVENTS_PATH, event)
    screen_width = event.get("gaze_screen_width") or event.get("screen_width")
    screen_height = event.get("gaze_screen_height") or event.get("screen_height")
    if isinstance(screen_width, (int, float)) and isinstance(screen_height, (int, float)):
        screen = SimpleNamespace(width=int(screen_width), height=int(screen_height))
        persist_drift_correction(recent_correction_events(limit=120), screen)
    return event


def recent_correction_events(limit: int = 80, reliable_only: bool = False) -> list[dict[str, Any]]:
    if not CORRECTION_EVENTS_PATH.exists():
        return []
    lines = CORRECTION_EVENTS_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            if reliable_only and not is_gaze_reliable_event(event):
                continue
            events.append(event)
    return events
