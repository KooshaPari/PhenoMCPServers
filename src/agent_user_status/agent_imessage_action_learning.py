#!/usr/bin/env python3
"""Action response learning helpers for agent-imessage."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from agent_user_status.agent_imessage_core import (
    ACTION_LEARNING_PATH,
    ACTION_LOG_PATH,
    LEARNING_PATH,
    clamp,
    iso_now,
    parse_dt,
    read_json_file,
    write_json_file,
)
from agent_user_status.gaze_context import is_gaze_reliable_event
from agent_user_status.jsonl_tail import tail_jsonl


def read_action_events(limit: int = 200) -> list[dict[str, Any]]:
    return tail_jsonl(ACTION_LOG_PATH, limit=limit)


def recent_action_records(reliable_only: bool = False) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    fresh: list[dict[str, Any]] = []
    for event in read_action_events():
        observed_at = parse_dt(event.get("observed_at"))
        max_age = int(event.get("max_age_seconds", 180))
        if observed_at and (now - observed_at).total_seconds() <= max_age:
            if reliable_only and not is_gaze_reliable_event(event):
                continue
            fresh.append(event)
    return fresh


def score_for_action(direction: str, kind: str, provided: float | None) -> tuple[float, str]:
    if provided is not None:
        return clamp(provided), "provided"
    key = f"{direction}:{kind}".lower().replace("-", "_")
    defaults = {
        "input:mouse_click": (0.88, "direct_input"),
        "input:key_press": (0.9, "direct_input"),
        "input:scroll": (0.78, "direct_input"),
        "input:window_focus": (0.72, "direct_input"),
        "output:video_playing": (0.28, "passive_media"),
        "output:audio_playing": (0.45, "background_media"),
        "output:meeting_active": (0.18, "busy_output"),
        "output:screenshare_active": (0.2, "busy_output"),
        "output:notification_sent": (0.5, "agent_output"),
        "output:agent_complete": (0.55, "agent_completed"),
        "output:agent_waiting_user": (0.62, "agent_waiting_for_user"),
        "output:agent_question": (0.66, "agent_question_pending"),
    }
    return defaults.get(key, (0.5, "action_observed"))


def action_signal() -> dict[str, Any] | None:
    records = recent_action_records(reliable_only=True)
    if not records:
        return None
    signal_records: list[dict[str, Any]] = []
    for record in records[-12:]:
        score = record.get("score")
        if isinstance(score, (int, float)):
            signal_records.append(
                {
                    "name": f"action:{record.get('direction')}:{record.get('kind')}",
                    "ok": True,
                    "score": float(score),
                    "weight": float(record.get("weight", 1.0)),
                    "state": record.get("state", "action_observed"),
                }
            )
    score = weighted_average(signal_records)
    if score is None:
        return None
    return {
        "name": "recent_actions",
        "ok": True,
        "score": score,
        "state": "recent_input_output_actions",
        "events": records[-8:],
    }


def action_learning_signal() -> dict[str, Any] | None:
    learning = read_json_file(ACTION_LEARNING_PATH)
    records = recent_action_records(reliable_only=True)
    if not learning or not records:
        return None
    scored: list[dict[str, Any]] = []
    for record in records[-12:]:
        stats = best_action_stats(learning.get("actions", {}), record)
        if not stats or int(stats.get("samples", 0)) < 2:
            continue
        if not is_gaze_reliable_event(record):
            continue
        key = str(stats.get("key") or f"{record.get('direction')}:{record.get('kind')}")
        median = float(stats.get("median_response_minutes", 999))
        if median <= 5:
            score = 0.85
        elif median <= 15:
            score = 0.65
        elif median <= 60:
            score = 0.35
        else:
            score = 0.15
        scored.append(
            {
                "name": f"learned_action:{key}",
                "ok": True,
                "score": score,
                "weight": 0.8,
                "state": "learned_action_response_pattern",
                "eta_minutes": int(round(median)),
                "samples": int(stats.get("samples", 0)),
            }
        )
    score = weighted_average(scored)
    if score is None:
        return None
    return {"name": "learned_actions", "ok": True, "score": score, "state": "action_learning", "signals": scored}


def best_action_stats(actions: dict[str, Any], event: dict[str, Any]) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for key in action_learning_keys(event):
        stats = actions.get(key)
        if isinstance(stats, dict):
            stats = {**stats, "key": key}
            candidates.append(stats)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            int(item.get("samples", 0)),
            -float(item.get("median_response_minutes", 999)),
        ),
    )


def action_learning_keys(event: dict[str, Any]) -> list[str]:
    direction = str(event.get("direction") or "unknown")
    kind = str(event.get("kind") or "unknown")
    base = f"{direction}:{kind}"
    keys = [base]
    state = str(event.get("state") or "")
    if state:
        keys.append(f"{base}:state:{state}")
    if event.get("gaze_targeting_reliable") is False:
        return keys
    if event.get("terminal_active"):
        keys.append(f"{base}:terminal")
    window_role = str(event.get("window_role") or "")
    if window_role:
        keys.append(f"{base}:window_role:{window_role}")
    frontmost = str(event.get("frontmost_app") or "").lower().replace(" ", "_")
    if frontmost:
        keys.append(f"{base}:app:{frontmost}")
    return keys


def learned_eta_from_signals(signals: list[dict[str, Any]]) -> int | None:
    values: list[int] = []
    for signal in signals:
        if isinstance(signal.get("eta_minutes"), int):
            values.append(int(signal["eta_minutes"]))
        nested = signal.get("signals")
        if isinstance(nested, list):
            values.extend(
                int(item["eta_minutes"])
                for item in nested
                if isinstance(item, dict) and isinstance(item.get("eta_minutes"), int)
            )
    if not values:
        return None
    values.sort()
    return values[min(len(values) - 1, len(values) // 2)]


def learning_prior() -> dict[str, Any] | None:
    data = read_json_file(LEARNING_PATH)
    if not data:
        return None
    samples = int(data.get("samples", 0))
    if samples < 3:
        return None
    median = data.get("median_response_minutes")
    if median is None:
        return None
    confidence = clamp(float(data.get("confidence", min(0.65, 0.3 + samples / 30))))
    return {
        "name": "learned_prior",
        "ok": True,
        "score": confidence,
        "state": "historical_response_pattern",
        "eta_minutes": int(median),
        "samples": samples,
    }


def weighted_average(records: Iterable[dict[str, Any]]) -> float | None:
    total = 0.0
    weight_sum = 0.0
    for record in records:
        if not record.get("ok", True):
            continue
        if "score" not in record:
            continue
        weight = float(record.get("weight", 1.0))
        total += float(record["score"]) * weight
        weight_sum += weight
    if weight_sum == 0:
        return None
    return clamp(total / weight_sum)


def update_action_learning(response_minutes: float, action_context: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "response_minutes": response_minutes,
        "learned_keys": [],
        "skipped_unreliable": 0,
        "considered": 0,
    }
    if not action_context:
        return summary

    data = read_json_file(ACTION_LEARNING_PATH) or {"actions": {}}
    actions = data.get("actions", {})
    if not isinstance(actions, dict):
        actions = {}

    for event in action_context[-12:]:
        summary["considered"] += 1
        if not is_gaze_reliable_event(event):
            summary["skipped_unreliable"] += 1
            continue
        for key in action_learning_keys(event):
            stats = actions.get(key, {})
            samples = list(stats.get("response_minutes", []))
            samples.append(response_minutes)
            samples = [float(value) for value in samples[-50:]]
            ordered = sorted(samples)
            mid = len(ordered) // 2
            median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
            actions[key] = {
                "samples": len(samples),
                "response_minutes": samples,
                "median_response_minutes": round(median),
                "last_response_minutes": response_minutes,
                "updated_at": iso_now(),
            }
            summary["learned_keys"].append(key)

    write_json_file(ACTION_LEARNING_PATH, {"actions": actions, "updated_at": iso_now()})
    summary["learned_keys"] = sorted(set(summary["learned_keys"]))
    return summary
