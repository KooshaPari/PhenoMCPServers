#!/usr/bin/env python3
"""CLI commands for the local iMessage helper."""

from __future__ import annotations

import argparse
import json
import sys
import time

from agent_user_status.agent_imessage_comm_commands import (
    add_comm_parsers,
)
from agent_user_status.agent_imessage_core import (
    RECIPIENT_ROLES,
    STATE_DIR,
    inbound_messages,
    load_config,
    load_recipient_config,
    recent_messages,
    recipient_send_address,
    run_imsg,
)
from agent_user_status.agent_imessage_outbox import latest_outbox_state, record_response_received
from agent_user_status.agent_imessage_presence_commands import add_presence_parsers
from agent_user_status.agent_imessage_session_commands import add_session_parsers
from agent_user_status.agent_imessage_state_commands import add_state_parsers
from agent_user_status.agent_imessage_status import (
    estimate_status,
    hook_decision_result,
)


def command_notify(args: argparse.Namespace) -> int:
    config = load_recipient_config(args.recipient)
    message = args.message or sys.stdin.read().strip()
    if not message:
        print("No message provided", file=sys.stderr)
        return 2
    try:
        address = recipient_send_address(config)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.dry_run:
        print(json.dumps({"recipient": config.role, "to": address, "name": config.name, "message": message}, indent=2))
        return 0
    result = run_imsg(["send", "--to", address, "--text", message, "--service", "auto"], timeout=60)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def command_inbox(args: argparse.Namespace) -> int:
    config = load_recipient_config(args.recipient)
    try:
        chat, messages = recent_messages(config, args.limit)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"recipient": config.role, "chat": chat, "messages": messages}, indent=2))
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


def command_hook_decision(args: argparse.Namespace) -> int:
    output = hook_decision_result(args.text or sys.stdin.read())
    print(json.dumps(output, indent=2))
    return 0


def command_wait(args: argparse.Namespace) -> int:
    config = load_recipient_config(args.recipient)
    state_file = STATE_DIR / f"last_seen_message_id_{config.role}"
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
                latest_outbound = latest_outbox_state(recipient=config.role)
                if latest_outbound:
                    record_response_received(
                        message_id=str(latest_outbound["message_id"]),
                        correlation_id=str(latest_outbound["correlation_id"]),
                        recipient=config.role,
                        response_id=latest_id,
                        response_body=str(latest.get("text") or ""),
                        note="inbound reply observed",
                    )
                print(json.dumps(latest, indent=2) if args.json else latest.get("text", ""))
                return 0
        time.sleep(args.poll)
    return 124


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agent iMessage helper")
    sub = parser.add_subparsers(dest="command", required=True)

    notify = sub.add_parser("notify", help="Send a message to a scoped configured recipient")
    notify.add_argument("message", nargs="?", help="Message text, or stdin when omitted")
    notify.add_argument("--recipient", choices=RECIPIENT_ROLES, default="koosha")
    notify.add_argument("--dry-run", action="store_true")
    notify.set_defaults(func=command_notify)

    add_comm_parsers(sub)

    inbox = sub.add_parser("inbox", help="Read recent scoped-recipient conversation")
    inbox.add_argument("--recipient", choices=RECIPIENT_ROLES, default="koosha")
    inbox.add_argument("--limit", type=int, default=20)
    inbox.add_argument("--json", action="store_true")
    inbox.set_defaults(func=command_inbox)

    status = sub.add_parser("status", help="Estimate whether user is likely to respond soon")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=command_status)

    add_presence_parsers(sub)

    hook_decision = sub.add_parser("hook-decision", help="Return stop-hook decision metadata")
    hook_decision.add_argument("--text")
    hook_decision.set_defaults(func=command_hook_decision)

    wait = sub.add_parser("wait", help="Wait for the next inbound message from a scoped recipient")
    wait.add_argument("--recipient", choices=RECIPIENT_ROLES, default="koosha")
    wait.add_argument("--timeout", type=int, default=900)
    wait.add_argument("--poll", type=float, default=3.0)
    wait.add_argument("--limit", type=int, default=20)
    wait.add_argument("--json", action="store_true")
    wait.add_argument("--include-existing", action="store_true")
    wait.set_defaults(func=command_wait)

    add_session_parsers(sub)
    add_state_parsers(sub)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))
