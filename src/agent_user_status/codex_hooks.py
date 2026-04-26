"""Codex lifecycle hook adapter for agent-imessage session telemetry."""

from __future__ import annotations

import json
import sys
from typing import Any

from agent_user_status.agent_imessage_status import hook_decision_result
from agent_user_status.session_registry import append_session_event, append_session_heartbeat

SUPPORTED_EVENTS = {
    "SessionStart",
    "PreToolUse",
    "PermissionRequest",
    "PostToolUse",
    "UserPromptSubmit",
    "Stop",
}


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "hook_event_name": _text(payload.get("hook_event_name"), "unknown"),
        "cwd": _text(payload.get("cwd")),
        "model": _text(payload.get("model")),
        "turn_id": _text(payload.get("turn_id")),
        "session_log_available": payload.get("transcript_path") is not None,
    }
    for key in ("source", "tool_name", "tool_use_id", "agent_id", "agent_type"):
        if payload.get(key) is not None:
            metadata[key] = _text(payload.get(key))
    if isinstance(payload.get("stop_hook_active"), bool):
        metadata["stop_hook_active"] = payload["stop_hook_active"]
    return metadata


def _session_id(payload: dict[str, Any]) -> str:
    return _text(payload.get("session_id"), "codex-hook")


def _agent_id(payload: dict[str, Any]) -> str:
    return _text(payload.get("agent_id") or payload.get("agent_type") or "codex", "codex")


def handle_codex_hook(payload: dict[str, Any]) -> dict[str, Any]:
    """Record a Codex hook event and return Codex-compatible JSON output."""
    event = _text(payload.get("hook_event_name"), "unknown")
    session_id = _session_id(payload)
    agent_id = _agent_id(payload)
    metadata = _metadata(payload)

    if event == "SessionStart":
        append_session_heartbeat(
            session_id,
            agent_id=agent_id,
            status="working",
            state=_text(payload.get("source"), "session_start"),
            note="codex_hook",
            metadata=metadata,
            ttl_seconds=900,
        )
        return {"continue": True}

    append_session_event(
        session_id,
        f"codex_{event.lower()}",
        agent_id=agent_id,
        state=_text(payload.get("tool_name") or payload.get("source") or event),
        note="codex_hook",
        metadata=metadata,
    )

    if event != "Stop":
        return {"continue": True}

    if bool(payload.get("stop_hook_active")):
        return {"continue": True, "systemMessage": "agent-imessage stop hook already continued this turn."}

    decision = hook_decision_result(_text(payload.get("last_assistant_message")))
    prompt = decision.get("prompt")
    if prompt and decision.get("decision") in {"reprompt_wait", "reprompt_default_or_defer"}:
        return {
            "decision": "block",
            "reason": str(prompt),
            "systemMessage": "agent-imessage stop hook requested one continuation pass.",
        }
    return {"continue": True}


def load_hook_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Codex hook JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Codex hook payload must be a JSON object")
    return payload


def main() -> int:
    try:
        payload = load_hook_payload(sys.stdin.read())
        output = handle_codex_hook(payload)
    except Exception as exc:  # Hook scripts must fail open unless explicitly blocking.
        output = {"continue": True, "systemMessage": f"agent-imessage hook failed open: {exc}"}
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
