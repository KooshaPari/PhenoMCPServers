#!/usr/bin/env python3
"""Action learning and workspace attribution helpers for agent-imessage."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Iterable

from agent_user_status.agent_imessage_core import (
    ACTION_LEARNING_PATH,
    ACTION_LOG_PATH,
    LEARNING_PATH,
    STATE_DIR,
    clamp,
    frontmost_app_signal,
    iso_now,
    parse_dt,
    process_activity_signal,
    read_json_file,
    write_json_file,
)
from agent_user_status.gaze_context import annotate_event_with_gaze, is_gaze_reliable_event


def read_action_events(limit: int = 200) -> list[dict[str, Any]]:
    if not ACTION_LOG_PATH.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in ACTION_LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def recent_action_records(reliable_only: bool = False) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
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


def hook_configuration_context() -> dict[str, bool]:
    claude_path = Path("~/.claude/settings.json").expanduser()
    codex_path = Path("~/.codex/AGENTS.md").expanduser()
    claude_text = claude_path.read_text(encoding="utf-8") if claude_path.exists() else ""
    codex_text = codex_path.read_text(encoding="utf-8") if codex_path.exists() else ""
    return {
        "claude_stop_hook": "agent-user-status-stop-hook" in claude_text and '"Stop"' in claude_text,
        "codex_hook_guidance": "User Response Status and iMessage" in codex_text
        and "hook-decision" in codex_text,
    }


def classify_window_role(frontmost_app: str | None, process_groups: dict[str, list[str]] | None = None) -> str:
    app = str(frontmost_app or "").lower()
    groups = process_groups or {}
    agent_count = len(groups.get("agent", []))
    coding_count = len(groups.get("coding", []))
    if any(token in app for token in ("messages", "imessage")):
        return "gui_chat"
    if any(token in app for token in ("claude", "codex", "chatgpt", "openai")):
        return "gui_agent"
    if any(token in app for token in ("safari", "chrome", "edge", "arc", "firefox")):
        return "browser"
    if any(token in app for token in ("slack", "zoom", "facetime", "messages")):
        return "communication"
    if any(token in app for token in ("music", "spotify", "tv", "quicktime", "vlc", "youtube")):
        return "media"
    if any(token in app for token in ("xcode", "cursor", "zed", "code", "vscode", "visual studio")):
        return "editor"
    if any(token in app for token in ("terminal", "ghostty", "iterm", "warp", "tmux", "screen", "shell", "pane")):
        if agent_count > 0 and coding_count > 0:
            return "multi_agent_terminal"
        if agent_count > 0:
            return "agent_terminal"
        if coding_count > 0:
            return "coding_terminal"
        return "terminal"
    return "unknown"


def action_environment_context() -> dict[str, Any]:
    frontmost = frontmost_app_signal()
    processes = process_activity_signal()
    groups = processes.get("process_groups") if processes.get("ok") else {}
    groups = groups if isinstance(groups, dict) else {}
    frontmost_app = frontmost.get("app") if frontmost.get("ok") else None
    app_text = str(frontmost_app or "").lower()
    terminal_active = any(token in app_text for token in ("terminal", "ghostty", "iterm", "warp"))
    window_role = classify_window_role(frontmost_app, {k: list(v) for k, v in groups.items() if isinstance(v, list)})
    context = {
        "frontmost_app": frontmost_app,
        "terminal_active": terminal_active,
        "window_role": window_role,
        "agent_processes": groups.get("agent", []),
        "coding_processes": groups.get("coding", []),
    }
    annotate_event_with_gaze(context)
    return context


def coarse_attribution_context() -> dict[str, Any]:
    context = action_environment_context()
    hook_config = hook_configuration_context()
    frontmost_app = str(context.get("frontmost_app") or "").lower()
    agent_processes = [str(item).lower() for item in context.get("agent_processes") or [] if item]
    coding_processes = [str(item).lower() for item in context.get("coding_processes") or [] if item]
    terminal_active = bool(context.get("terminal_active"))
    window_role = str(context.get("window_role") or "unknown")
    gaze_reliable = bool(context.get("gaze_targeting_reliable"))

    surface = "unknown"
    confidence = 0.0
    hook_status = "not_applicable"
    reasons: list[str] = []

    if any(token in frontmost_app for token in ("messages", "imessage")):
        surface = "gui_chat"
        confidence = 0.91
        hook_status = "gui_chat"
        reasons.append("frontmost_messages_chat")
    elif any(token in frontmost_app for token in ("claude", "codex", "chatgpt", "openai")):
        surface = "gui_agent_chat"
        confidence = 0.86
        hook_status = (
            "gui_agent_configured"
            if (
                ("claude" in frontmost_app and hook_config["claude_stop_hook"]) or
                ("codex" in frontmost_app and hook_config["codex_hook_guidance"])
            )
            else "gui_agent_unverified"
        )
        reasons.append("frontmost_agent_chat_app")
    elif terminal_active:
        if agent_processes and coding_processes:
            surface = "multi_agent_terminal_candidate"
            confidence = 0.68
            hook_status = (
                "candidate_configured"
                if (hook_config["claude_stop_hook"] or hook_config["codex_hook_guidance"])
                else "candidate_unverified"
            )
            reasons.append("terminal_with_agent_and_coding_processes")
        elif agent_processes:
            surface = "agent_terminal_candidate"
            confidence = 0.63
            hook_status = (
                "candidate_configured"
                if (hook_config["claude_stop_hook"] or hook_config["codex_hook_guidance"])
                else "candidate_unverified"
            )
            reasons.append("terminal_with_agent_processes")
        elif coding_processes:
            surface = "coding_terminal_candidate"
            confidence = 0.48
            hook_status = "unreliable_terminal_identity"
            reasons.append("terminal_with_coding_processes_only")
        else:
            surface = "unresolved_terminal"
            confidence = 0.34
            hook_status = "unreliable_terminal_identity"
            reasons.append("terminal_without_agent_process_hint")
    elif window_role == "editor":
        surface = "coding_workspace_candidate"
        confidence = 0.6
        hook_status = "unreliable_terminal_identity"
        reasons.append("editor_window_active")
    elif window_role == "browser":
        surface = "browser_workspace_candidate"
        confidence = 0.42
        hook_status = "not_applicable"
        reasons.append("browser_window_active")
    elif agent_processes:
        surface = "background_agent_workspace_candidate"
        confidence = 0.66
        hook_status = (
            "candidate_configured"
            if (hook_config["claude_stop_hook"] or hook_config["codex_hook_guidance"])
            else "candidate_unverified"
        )
        reasons.append("agent_processes_without_terminal_focus")
    elif coding_processes:
        surface = "background_coding_workspace_candidate"
        confidence = 0.5
        hook_status = "unreliable_terminal_identity"
        reasons.append("coding_processes_without_terminal_focus")

    reliable = confidence >= 0.7 and not hook_status.startswith("unreliable") and gaze_reliable
    if not gaze_reliable:
        reasons.append("gaze_unreliable")

    context.update(
        {
            "surface": surface,
            "confidence": round(confidence, 2),
            "reliable": reliable,
            "hook_status": hook_status,
            "window_role": window_role,
            "reasons": reasons,
            "hook_configuration": hook_config,
        }
    )
    return context


def attribution_status_text(context: dict[str, Any]) -> str:
    surface = str(context.get("surface") or "unknown")
    hook_status = str(context.get("hook_status") or "unknown")
    reasons = ",".join(str(item) for item in context.get("reasons") or [] if item)
    if context.get("reliable"):
        return f"{surface}:{hook_status}"
    if surface != "unknown" or hook_status != "unknown":
        base = f"uncertain:{surface}:{hook_status}"
        if reasons:
            return f"{base}:{reasons}"
        return base
    if reasons:
        return f"uncertain:{reasons}"
    return "uncertain:unknown"


def append_action_event(
    direction: str,
    kind: str,
    score: float | None = None,
    weight: float = 1.0,
    state: str | None = None,
    eta_minutes: int | None = None,
    max_age_seconds: int = 180,
    note: str | None = None,
) -> dict[str, Any]:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    normalized_kind = kind.replace("-", "_")
    event_score, default_state = score_for_action(direction, normalized_kind, score)
    event = {
        "observed_at": iso_now(),
        "direction": direction,
        "kind": normalized_kind,
        "score": event_score,
        "weight": weight,
        "state": state or default_state,
        "eta_minutes": eta_minutes,
        "max_age_seconds": max_age_seconds,
        "note": note,
        **action_environment_context(),
    }
    with ACTION_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")
    return event


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
