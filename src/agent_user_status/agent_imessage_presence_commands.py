"""Presence, action, and response-learning CLI commands for agent-imessage."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from agent_user_status.agent_imessage_core import (
    ACTION_LEARNING_PATH,
    LEARNING_PATH,
    OVERRIDE_PATH,
    RESPONSE_LOG_PATH,
    SIGNALS_PATH,
    STATE_DIR,
    clamp,
    external_signal_records,
    frontmost_app_signal,
    idle_time_signal,
    iso_now,
    load_config,
    media_activity_signal,
    process_activity_signal,
    read_json_file,
    validate_abstract_payload,
    write_json_file,
)
from agent_user_status.agent_imessage_learning import (
    append_action_event,
    coarse_attribution_context,
    learning_prior,
    recent_action_records,
    update_action_learning,
)
from agent_user_status.agent_imessage_status import estimate_status, status_from_override
from agent_user_status.jsonl_tail import tail_jsonl


def command_set_status(args: argparse.Namespace) -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    until: str | None = None
    if args.minutes:
        until = (datetime.now(UTC) + timedelta(minutes=args.minutes)).isoformat()
    confidence = args.confidence
    if confidence is None:
        confidence = {
            "active": 0.9,
            "near": 0.75,
            "away": 0.2,
            "focus": 0.2,
            "sleep": 0.05,
            "async": 0.1,
            "unknown": 0.0,
        }[args.mode]
    payload = {
        "mode": args.mode,
        "confidence": confidence,
        "eta_minutes": args.eta_minutes,
        "estimated_response": args.eta,
        "until": until,
        "note": args.note,
        "updated_at": iso_now(),
    }
    OVERRIDE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(status_from_override(payload), indent=2))
    return 0


def command_clear_status(args: argparse.Namespace) -> int:
    if OVERRIDE_PATH.exists():
        OVERRIDE_PATH.unlink()
    print(json.dumps({"ok": True, "cleared": True}, indent=2))
    return 0


def command_signal(args: argparse.Namespace) -> int:
    try:
        validate_abstract_payload(args.name, args.state, args.note)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = read_json_file(SIGNALS_PATH) or {"signals": []}
    records = data.get("signals", [])
    if not isinstance(records, list):
        records = []
    record = {
        "name": args.name,
        "ok": True,
        "score": clamp(args.score),
        "weight": args.weight,
        "state": args.state,
        "eta_minutes": args.eta_minutes,
        "observed_at": iso_now(),
        "max_age_seconds": args.max_age_seconds,
        "note": args.note,
    }
    records = [r for r in records if isinstance(r, dict) and r.get("name") != args.name]
    records.append(record)
    write_json_file(SIGNALS_PATH, {"signals": records})
    print(json.dumps(record, indent=2))
    return 0


def command_signals(args: argparse.Namespace) -> int:
    payload = {
        "built_in": [idle_time_signal(), frontmost_app_signal(), process_activity_signal(), media_activity_signal()],
        "actions": recent_action_records(),
        "action_learning": read_json_file(ACTION_LEARNING_PATH),
        "external": external_signal_records(),
        "learning": learning_prior(),
    }
    print(json.dumps(payload, indent=2))
    return 0


def command_clear_signal(args: argparse.Namespace) -> int:
    data = read_json_file(SIGNALS_PATH) or {"signals": []}
    records = data.get("signals", [])
    if not isinstance(records, list):
        records = []
    kept = [r for r in records if isinstance(r, dict) and r.get("name") != args.name]
    write_json_file(SIGNALS_PATH, {"signals": kept})
    print(json.dumps({"ok": True, "cleared": args.name, "remaining": len(kept)}, indent=2))
    return 0


def command_log_response(args: argparse.Namespace) -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "observed_at": iso_now(),
        "response_minutes": args.response_minutes,
        "source": args.source,
        "note": args.note,
        "action_context": recent_action_records(reliable_only=True),
    }
    with RESPONSE_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")

    events: list[dict[str, Any]] = []
    for item in tail_jsonl(RESPONSE_LOG_PATH, limit=200):
        if isinstance(item.get("response_minutes"), (int, float)):
            events.append(item)
    values = sorted(float(item["response_minutes"]) for item in events)
    if not values:
        print(json.dumps({"ok": True, "event": event}, indent=2))
        return 0
    mid = len(values) // 2
    median = values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2
    learned = {
        "samples": len(values),
        "median_response_minutes": round(median),
        "p80_response_minutes": round(values[min(len(values) - 1, int(len(values) * 0.8))]),
        "confidence": clamp(0.3 + len(values) / 30),
        "updated_at": iso_now(),
    }
    write_json_file(LEARNING_PATH, learned)
    learning_update = update_action_learning(float(args.response_minutes), event["action_context"])
    print(json.dumps({"ok": True, "event": event, "learning": learned, "learning_update": learning_update}, indent=2))
    return 0


def command_action(args: argparse.Namespace) -> int:
    try:
        validate_abstract_payload(args.direction, args.kind, args.state, args.note)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    event = append_action_event(
        direction=args.direction,
        kind=args.kind,
        score=args.score,
        weight=args.weight,
        state=args.state,
        eta_minutes=args.eta_minutes,
        max_age_seconds=args.max_age_seconds,
        note=args.note,
    )
    print(json.dumps({"ok": True, "event": event, "status": estimate_status(load_config())}, indent=2))
    return 0


def command_actions(args: argparse.Namespace) -> int:
    payload = {
        "attribution": coarse_attribution_context(),
        "recent": recent_action_records(),
        "recent_reliable": recent_action_records(reliable_only=True),
        "learning": read_json_file(ACTION_LEARNING_PATH),
    }
    print(json.dumps(payload, indent=2))
    return 0


def add_presence_parsers(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    set_status = sub.add_parser("set-status", help="Set manual response-likelihood override")
    set_status.add_argument("mode", choices=["active", "near", "away", "focus", "sleep", "async", "unknown"])
    set_status.add_argument("--minutes", type=int, default=60, help="Override lifetime")
    set_status.add_argument("--eta-minutes", type=int)
    set_status.add_argument("--eta")
    set_status.add_argument("--confidence", type=float)
    set_status.add_argument("--note")
    set_status.set_defaults(func=command_set_status)

    clear_status = sub.add_parser("clear-status", help="Clear manual response-likelihood override")
    clear_status.set_defaults(func=command_clear_status)

    signal = sub.add_parser("signal", help="Record an external presence signal")
    signal.add_argument("name", help="Signal name, e.g. eye_tracking or meeting_status")
    signal.add_argument("--score", type=float, required=True, help="0.0 away to 1.0 active")
    signal.add_argument("--weight", type=float, default=1.0)
    signal.add_argument("--state", default="external")
    signal.add_argument("--eta-minutes", type=int)
    signal.add_argument("--max-age-seconds", type=int, default=300)
    signal.add_argument("--note")
    signal.set_defaults(func=command_signal)

    signals = sub.add_parser("signals", help="Inspect built-in and external status signals")
    signals.set_defaults(func=command_signals)

    clear_signal = sub.add_parser("clear-signal", help="Clear an external presence signal")
    clear_signal.add_argument("name")
    clear_signal.set_defaults(func=command_clear_signal)

    log_response = sub.add_parser("log-response", help="Record observed response latency for learning")
    log_response.add_argument("response_minutes", type=float)
    log_response.add_argument("--source", default="manual")
    log_response.add_argument("--note")
    log_response.set_defaults(func=command_log_response)

    action = sub.add_parser("action", help="Record an input/output action for response-likelihood learning")
    action.add_argument("direction", choices=["input", "output"], help="Observed action direction")
    action.add_argument("kind", help="Action kind, e.g. mouse_click, key_press, video_playing")
    action.add_argument("--score", type=float, help="0.0 away/busy to 1.0 actively reachable")
    action.add_argument("--weight", type=float, default=1.0)
    action.add_argument("--state")
    action.add_argument("--eta-minutes", type=int)
    action.add_argument("--max-age-seconds", type=int, default=180)
    action.add_argument("--note")
    action.set_defaults(func=command_action)

    actions = sub.add_parser("actions", help="Inspect recent action events and per-action learning")
    actions.set_defaults(func=command_actions)
