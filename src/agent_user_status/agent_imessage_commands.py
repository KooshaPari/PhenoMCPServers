#!/usr/bin/env python3
"""CLI commands for the local iMessage helper."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from agent_user_status.agent_imessage_core import (
    ACTION_LEARNING_PATH,
    LEARNING_PATH,
    OVERRIDE_PATH,
    RESPONSE_LOG_PATH,
    SIGNALS_PATH,
    STATE_DIR,
    clamp,
    eta_label,
    frontmost_app_signal,
    idle_time_signal,
    inbound_messages,
    iso_now,
    load_config,
    media_activity_signal,
    process_activity_signal,
    external_signal_records,
    read_json_file,
    recent_messages,
    run_imsg,
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
from agent_user_status.agent_imessage_status import (
    estimate_status,
    hook_decision_result,
    status_from_override,
)


def command_notify(args: argparse.Namespace) -> int:
    config = load_config()
    message = args.message or sys.stdin.read().strip()
    if not message:
        print("No message provided", file=sys.stderr)
        return 2
    if args.dry_run:
        print(json.dumps({"to": config.phone_e164, "message": message}, indent=2))
        return 0
    result = run_imsg(["send", "--to", config.phone_e164, "--text", message, "--service", "auto"], timeout=60)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def command_inbox(args: argparse.Namespace) -> int:
    config = load_config()
    try:
        chat, messages = recent_messages(config, args.limit)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"chat": chat, "messages": messages}, indent=2))
        return 0
    for msg in messages:
        direction = "agent" if msg.get("is_from_me") else "user"
        print(f"{msg.get('created_at')} {direction}: {msg.get('text') or ''}")
    return 0


def command_status(args: argparse.Namespace) -> int:
    status = estimate_status(load_config())
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(
            f"{status['status']} confidence={status['confidence']} "
            f"eta={status['estimated_response']} reason={status.get('reason', '')}"
        )
    return 0 if status.get("ok") else 1


def command_set_status(args: argparse.Namespace) -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    until: str | None = None
    if args.minutes:
        until = (datetime.now(timezone.utc) + timedelta(minutes=args.minutes)).isoformat()
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
    if RESPONSE_LOG_PATH.exists():
        for line in RESPONSE_LOG_PATH.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item.get("response_minutes"), (int, float)):
                events.append(item)
    values = sorted(float(item["response_minutes"]) for item in events)
    if values:
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
        print(
            json.dumps(
                {
                    "ok": True,
                    "event": event,
                    "learning": learned,
                    "learning_update": learning_update,
                },
                indent=2,
            )
        )
    else:
        print(json.dumps({"ok": True, "event": event}, indent=2))
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


def command_hook_decision(args: argparse.Namespace) -> int:
    output = hook_decision_result(args.text or sys.stdin.read())
    print(json.dumps(output, indent=2))
    return 0


def command_wait(args: argparse.Namespace) -> int:
    config = load_config()
    state_file = STATE_DIR / "last_seen_message_id"
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    last_seen = state_file.read_text(encoding="utf-8").strip() if state_file.exists() else ""

    if not last_seen and not args.include_existing:
        try:
            _, initial_messages = recent_messages(config, args.limit)
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
        initial_inbound = inbound_messages(config, initial_messages)
        if initial_inbound:
            latest = initial_inbound[-1]
            last_seen = str(latest.get("id") or latest.get("guid") or "")
            if last_seen:
                state_file.write_text(last_seen, encoding="utf-8")

    while time.monotonic() - start < args.timeout:
        try:
            _, messages = recent_messages(config, args.limit)
        except Exception as exc:
            print(str(exc), file=sys.stderr)
            return 1
        inbound = inbound_messages(config, messages)
        if inbound:
            latest = inbound[-1]
            latest_id = str(latest.get("id") or latest.get("guid") or "")
            if latest_id and latest_id != last_seen:
                state_file.write_text(latest_id, encoding="utf-8")
                print(json.dumps(latest, indent=2) if args.json else latest.get("text", ""))
                return 0
        time.sleep(args.poll)
    return 124


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent iMessage helper")
    sub = parser.add_subparsers(dest="command", required=True)

    notify = sub.add_parser("notify", help="Send a message to the configured user")
    notify.add_argument("message", nargs="?", help="Message text, or stdin when omitted")
    notify.add_argument("--dry-run", action="store_true")
    notify.set_defaults(func=command_notify)

    inbox = sub.add_parser("inbox", help="Read recent configured-user conversation")
    inbox.add_argument("--limit", type=int, default=20)
    inbox.add_argument("--json", action="store_true")
    inbox.set_defaults(func=command_inbox)

    status = sub.add_parser("status", help="Estimate whether user is likely to respond soon")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

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

    hook_decision = sub.add_parser("hook-decision", help="Return stop-hook decision metadata")
    hook_decision.add_argument("--text")
    hook_decision.set_defaults(func=command_hook_decision)

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

    wait = sub.add_parser("wait", help="Wait for the next inbound message")
    wait.add_argument("--timeout", type=int, default=900)
    wait.add_argument("--poll", type=float, default=3.0)
    wait.add_argument("--limit", type=int, default=20)
    wait.add_argument("--json", action="store_true")
    wait.add_argument("--include-existing", action="store_true")
    wait.set_defaults(func=command_wait)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))
