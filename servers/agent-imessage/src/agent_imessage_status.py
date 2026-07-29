#!/usr/bin/env python3
"""Status estimation and stop-hook decisions for agent-imessage."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from agent_user_status.agent_imessage_core import (
    STATE_DIR,
    WAITING_PATTERNS,
    Config,
    clamp,
    eta_label,
    external_signal_records,
    frontmost_app_signal,
    idle_time_signal,
    inbound_messages,
    load_config,
    media_activity_signal,
    parse_dt,
    process_activity_signal,
    read_presence_override,
    recent_messages,
    recommendation_for,
    stable_hash,
)
from agent_user_status.agent_imessage_learning import (
    action_learning_signal,
    action_signal,
    append_action_event,
    attribution_status_text,
    coarse_attribution_context,
    learned_eta_from_signals,
    learning_prior,
    weighted_average,
)
from agent_user_status.optional_dependencies import is_imessage_available
from agent_user_status.session_registry import append_session_event

_UNAVAILABLE_STATUS: dict[str, Any] = {
    "ok": True,
    "source": "imessage_unavailable",
    "status": "unknown",
    "confidence": 0.0,
    "estimated_response": "unknown",
    "recommendation": "use_judgment",
}


def _ensure_imessage() -> bool:
    """Return True when imessage is reachable. Callers use this to short-circuit
    heavy imessage-only paths and emit safe defaults."""
    return is_imessage_available()


def status_from_override(override: dict[str, Any]) -> dict[str, Any]:
    mode = override.get("mode", "unknown")
    eta_minutes = override.get("eta_minutes")
    confidence = float(override.get("confidence", 0.0))
    eta = eta_label(int(eta_minutes)) if eta_minutes is not None else override.get("estimated_response", "unknown")
    recommendation = recommendation_for(confidence, mode)

    return {
        "ok": True,
        "source": "manual_override",
        "status": mode,
        "confidence": confidence,
        "estimated_response": eta,
        "eta_minutes": eta_minutes,
        "recommendation": recommendation,
        "override_until": override.get("until"),
        "note": override.get("note"),
        "updated_at": override.get("updated_at"),
    }


def estimate_status(config: Config) -> dict[str, Any]:
    if not _ensure_imessage():
        return dict(_UNAVAILABLE_STATUS)
    override = read_presence_override()
    if override:
        return status_from_override(override)

    now = datetime.now(UTC)
    signals = [
        idle_time_signal(),
        frontmost_app_signal(),
        process_activity_signal(),
        media_activity_signal(),
        *external_signal_records(),
    ]
    recent_actions = action_signal()
    if recent_actions:
        signals.append(recent_actions)
    learned_actions = action_learning_signal()
    if learned_actions:
        signals.append(learned_actions)
    learned = learning_prior()
    if learned:
        signals.append(learned)
    learned_eta = learned_eta_from_signals(signals)

    signal_confidence = weighted_average(signals)
    signal_reasons = [s for s in signals if s.get("ok")]
    try:
        chat, messages = recent_messages(config, 25)
    except Exception as exc:
        confidence = signal_confidence if signal_confidence is not None else 0.0
        if confidence >= 0.72:
            status, eta = "active_by_device", "2-10 min"
        elif confidence >= 0.45:
            status, eta = "maybe_near", "10-30 min"
        elif confidence > 0:
            status, eta = "away_or_async", "30+ min"
        else:
            status, eta = "unknown", "unknown"
        if learned_eta is not None:
            eta = eta_label(learned_eta)
        return {
            "ok": signal_confidence is not None,
            "source": "device_signals",
            "status": status,
            "confidence": round(confidence, 2),
            "estimated_response": eta,
            "recommendation": recommendation_for(confidence, status),
            "reason": str(exc),
            "permission_hint": "Grant Full Disk Access to the terminal/app running the agent.",
            "signals": signal_reasons,
        }

    inbound = inbound_messages(config, messages)
    latest = inbound[-1] if inbound else None
    latest_at = parse_dt(latest.get("created_at")) if latest else None
    age_minutes = ((now - latest_at).total_seconds() / 60) if latest_at else None

    if age_minutes is None:
        status, confidence, eta = "unknown", 0.0, "unknown"
    elif age_minutes <= 5:
        status, confidence, eta = "active", 0.9, "0-2 min"
    elif age_minutes <= 20:
        status, confidence, eta = "likely_near", 0.72, "2-10 min"
    elif age_minutes <= 60:
        status, confidence, eta = "maybe_near", 0.45, "10-30 min"
    elif age_minutes <= 180:
        status, confidence, eta = "away_or_async", 0.25, "30+ min"
    else:
        status, confidence, eta = "async", 0.1, "unknown"

    if signal_confidence is not None:
        confidence = clamp((confidence * 0.65) + (signal_confidence * 0.35))
    if learned_eta is not None and (age_minutes is None or age_minutes > 20):
        eta = eta_label(learned_eta)

    recommendation = recommendation_for(confidence, status)

    return {
        "ok": True,
        "source": "imessage",
        "status": status,
        "confidence": round(confidence, 2),
        "estimated_response": eta,
        "recommendation": recommendation,
        "latest_inbound_at": latest.get("created_at") if latest else None,
        "latest_inbound_age_minutes": round(age_minutes, 1) if age_minutes is not None else None,
        "latest_inbound_preview": (latest.get("text") or "")[:160] if latest else None,
        "signals": signal_reasons,
        "chat": chat,
    }


def hook_decision_result(text: str) -> dict[str, Any]:
    if not _ensure_imessage():
        return {"ok": True, "decision": "allow", "reason": "imessage_disabled", "status": dict(_UNAVAILABLE_STATUS)}
    status = estimate_status(load_config())
    attribution = coarse_attribution_context()
    waiting = bool(WAITING_PATTERNS.search(text or ""))
    fingerprint = stable_hash(text or "")
    hook_state = STATE_DIR / "last_stop_hook_fingerprint"
    previous = hook_state.read_text(encoding="utf-8").strip() if hook_state.exists() else ""

    confidence = float(status.get("confidence") or 0.0)
    if not waiting:
        decision = "allow_stop"
        prompt = None
    elif previous == fingerprint:
        decision = "allow_stop"
        prompt = None
    elif confidence >= 0.7:
        attribution_text = attribution_status_text(attribution)
        attribution_note = (
            " Attribution is uncertain; prefer defaults over guessing."
            if not attribution.get("reliable")
            else ""
        )
        decision = "reprompt_wait"
        prompt = (
            "You appear to be waiting for Koosha. User status says he is likely "
            f"to respond soon (eta={status.get('estimated_response')}, "
            f"confidence={confidence}, source={status.get('source')}). "
            f"Workspace attribution is {attribution_text}.{attribution_note} "
            "Say clearly that you are waiting for his response only if the answer is actually needed. "
            "If you can safely continue without it, make the default decision and proceed."
        )
    else:
        attribution_text = attribution_status_text(attribution)
        attribution_note = (
            " Attribution is uncertain; do not promote unresolved terminals to a specific agent identity."
            if not attribution.get("reliable")
            else ""
        )
        decision = "reprompt_default_or_defer"
        prompt = (
            "You appear to be waiting for Koosha, but user status does not indicate "
            f"a near reply (status={status.get('status')}, eta={status.get('estimated_response')}, "
            f"confidence={confidence}, source={status.get('source')}). "
            f"Workspace attribution is {attribution_text}.{attribution_note} "
            "Do not stall. "
            "Answer your own question with a reasonable default, skip the optional work, "
            "or defer the question into the final answer unless this is a true external blocker."
        )

    if waiting and previous != fingerprint:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        hook_state.write_text(fingerprint, encoding="utf-8")

    event_kind = "agent_waiting_user" if waiting else "agent_complete"
    event_state = decision if waiting else "allow_stop"
    action_event = append_action_event(
        direction="output",
        kind=event_kind,
        score=None,
        weight=1.2 if waiting else 0.7,
        state=event_state,
        max_age_seconds=900,
        note="stop_hook",
    )
    session_event = append_session_event(
        os.environ.get("AGENT_USER_STATUS_SESSION_ID", "local-stop-hook"),
        event_kind,
        agent_id=os.environ.get("AGENT_USER_STATUS_AGENT_ID", "agent-imessage-hook"),
        state=event_state,
        note="stop_hook",
        metadata={
            "decision": decision,
            "waiting_detected": waiting,
            "attribution_surface": attribution.get("surface"),
            "attribution_reliable": attribution.get("reliable"),
            "hook_status": attribution.get("hook_status"),
            "status": status.get("status"),
            "estimated_response": status.get("estimated_response"),
        },
    )

    return {
        "ok": True,
        "waiting_detected": waiting,
        "decision": decision,
        "prompt": prompt,
        "status": status,
        "attribution": attribution,
        "action_event": action_event,
        "session_event": session_event,
        "fingerprint": fingerprint if waiting else None,
    }
