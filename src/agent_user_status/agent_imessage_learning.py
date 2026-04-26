#!/usr/bin/env python3
"""Action learning and workspace attribution helpers for agent-imessage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_user_status.agent_imessage_action_learning import (
    action_learning_keys,
    action_learning_signal,
    action_signal,
    best_action_stats,
    learned_eta_from_signals,
    learning_prior,
    read_action_events,
    recent_action_records,
    score_for_action,
    update_action_learning,
    weighted_average,
)
from agent_user_status.agent_imessage_core import (
    ACTION_LOG_PATH,
    STATE_DIR,
    frontmost_app_signal,
    iso_now,
    process_activity_signal,
)
from agent_user_status.gaze_context import annotate_event_with_gaze

__all__ = [
    "action_environment_context",
    "action_learning_keys",
    "action_learning_signal",
    "action_signal",
    "append_action_event",
    "attribution_status_text",
    "best_action_stats",
    "classify_window_role",
    "coarse_attribution_context",
    "hook_configuration_context",
    "learned_eta_from_signals",
    "learning_prior",
    "read_action_events",
    "recent_action_records",
    "score_for_action",
    "update_action_learning",
    "weighted_average",
]


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
