"""Structured communication CLI commands for agent-imessage."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys

from agent_user_status.agent_imessage_core import (
    RECIPIENT_ROLES,
    load_recipient_config,
    recipient_send_address,
    run_cmd,
    run_imsg,
)
from agent_user_status.agent_imessage_elicitation import ElicitationSchema, parse_reply
from agent_user_status.agent_imessage_envelope import AgentMessageEnvelope
from agent_user_status.agent_imessage_outbox import (
    append_outbox_record,
    delivery_record_from_envelope,
    latest_outbox_state,
    read_outbox_records,
    record_delivery_receipt,
    record_echo_cleanup_deleted,
    record_echo_cleanup_failed,
    record_echo_cleanup_requested,
    record_echo_cleanup_unsupported,
    sweep_expired_outbox_records,
)


def _load_answer_schema(value: str | None) -> ElicitationSchema | None:
    if not value:
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid answer schema JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Answer schema JSON must be an object")
    return ElicitationSchema.from_dict(payload)


def command_notify_structured(args: argparse.Namespace) -> int:
    config = load_recipient_config(args.recipient)
    message = args.message or sys.stdin.read().strip()
    try:
        answer_schema = _load_answer_schema(args.answer_schema_json)
        envelope = AgentMessageEnvelope.create(
            message,
            sender_name=args.sender_name,
            sender_kind=args.sender_kind,
            session_id=args.session_id,
            task_id=args.task_id or "",
            project=args.project or "",
            repo_path=args.repo_path or "",
            urgency=args.urgency,
            expires_minutes=args.expires_minutes,
            answer_schema=answer_schema,
            correlation_id=args.correlation_id,
        )
        address = recipient_send_address(config)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    rendered = envelope.render()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "recipient": config.role,
                    "to": address,
                    "name": config.name,
                    "envelope": envelope.to_dict(),
                    "rendered_message": rendered,
                },
                indent=2,
            )
        )
        return 0
    append_outbox_record(
        delivery_record_from_envelope(
            envelope,
            recipient=config.role,
            rendered_message=rendered,
            delivery_state="queued",
            note="queued for delivery",
        )
    )
    result = run_imsg(["send", "--to", address, "--text", rendered, "--service", "auto"], timeout=60)
    append_outbox_record(
        delivery_record_from_envelope(
            envelope,
            recipient=config.role,
            rendered_message=rendered,
            delivery_state="sent" if result.returncode == 0 else "failed",
            note=(result.stderr or result.stdout or "")[:240],
        )
    )
    if result.returncode == 0:
        record_delivery_receipt(
            message_id=envelope.message_id,
            correlation_id=envelope.correlation_id,
            recipient=config.role,
            receipt_id=envelope.message_id,
            note="send completed",
        )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode


def command_parse_reply(args: argparse.Namespace) -> int:
    try:
        schema = _load_answer_schema(args.answer_schema_json)
        if schema is None:
            raise ValueError("--answer-schema-json is required")
        parsed = parse_reply(args.reply or sys.stdin.read(), schema)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(parsed.to_dict(), indent=2))
    return 0


def command_outbox(args: argparse.Namespace) -> int:
    if args.sweep_expired:
        sweep_expired_outbox_records()
    records = read_outbox_records(
        correlation_id=args.correlation_id,
        message_id=args.message_id,
        recipient=args.recipient,
        limit=args.limit,
    )
    print(json.dumps({"records": records, "latest": records[-1] if records else None}, indent=2))
    return 0


def command_echo_delete(args: argparse.Namespace) -> int:
    if not args.correlation_id and not args.message_id:
        print("Specify --correlation-id or --message-id", file=sys.stderr)
        return 2
    latest = latest_outbox_state(correlation_id=args.correlation_id, message_id=args.message_id)
    if not latest:
        print(json.dumps({"ok": False, "error": "message_not_found"}, indent=2))
        return 1
    message_id = str(latest["message_id"])
    correlation_id = str(latest["correlation_id"])
    recipient = str(latest["recipient"])
    method = "configured-command"
    record_echo_cleanup_requested(
        message_id=message_id,
        correlation_id=correlation_id,
        recipient=recipient,
        method=method,
        note="echo cleanup requested",
    )
    template = os.environ.get("AGENT_IMESSAGE_ECHO_DELETE_CMD", "").strip()
    if not template:
        record = record_echo_cleanup_unsupported(
            message_id=message_id,
            correlation_id=correlation_id,
            recipient=recipient,
            reason=(
                "Sender-side Messages deletion is not configured. "
                "Set AGENT_IMESSAGE_ECHO_DELETE_CMD to a local delete helper."
            ),
        )
        print(json.dumps({"ok": True, "echo_cleanup": record}, indent=2))
        return 0
    formatted = template.format(
        message_id=message_id,
        correlation_id=correlation_id,
        recipient=recipient,
        project=str(latest.get("project") or ""),
        task_id=str(latest.get("task_id") or ""),
    )
    result = run_cmd(shlex.split(formatted), timeout=30)
    if result.returncode == 0:
        record = record_echo_cleanup_deleted(
            message_id=message_id,
            correlation_id=correlation_id,
            recipient=recipient,
            method=method,
            note="echo cleanup completed",
        )
        print(json.dumps({"ok": True, "echo_cleanup": record}, indent=2))
        return 0
    record = record_echo_cleanup_failed(
        message_id=message_id,
        correlation_id=correlation_id,
        recipient=recipient,
        reason=(result.stderr or result.stdout or "echo cleanup failed")[:240],
        method=method,
    )
    print(json.dumps({"ok": False, "echo_cleanup": record}, indent=2))
    return 1


def add_comm_parsers(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    notify_structured = sub.add_parser("notify-structured", help="Send a structured message envelope")
    notify_structured.add_argument("message", nargs="?", help="Message text, or stdin when omitted")
    notify_structured.add_argument("--recipient", choices=RECIPIENT_ROLES, default="koosha")
    notify_structured.add_argument("--sender-name", default="codex")
    notify_structured.add_argument("--sender-kind", default="codex")
    notify_structured.add_argument("--session-id")
    notify_structured.add_argument("--task-id")
    notify_structured.add_argument("--project")
    notify_structured.add_argument("--repo-path")
    notify_structured.add_argument("--urgency", choices=["low", "normal", "high", "urgent"], default="normal")
    notify_structured.add_argument("--expires-minutes", type=int)
    notify_structured.add_argument("--correlation-id")
    notify_structured.add_argument("--answer-schema-json")
    notify_structured.add_argument("--dry-run", action="store_true")
    notify_structured.set_defaults(func=command_notify_structured)

    parse_reply_cmd = sub.add_parser("parse-reply", help="Parse A1/A2/A3 reply text against an answer schema")
    parse_reply_cmd.add_argument("reply", nargs="?", help="Reply text, or stdin when omitted")
    parse_reply_cmd.add_argument("--answer-schema-json", required=True)
    parse_reply_cmd.set_defaults(func=command_parse_reply)

    outbox = sub.add_parser("outbox", help="Inspect structured outbound message lifecycle records")
    outbox.add_argument("--correlation-id")
    outbox.add_argument("--message-id")
    outbox.add_argument("--recipient", choices=RECIPIENT_ROLES)
    outbox.add_argument("--limit", type=int, default=200)
    outbox.add_argument("--sweep-expired", action="store_true")
    outbox.set_defaults(func=command_outbox)

    echo_delete = sub.add_parser("echo-delete", help="Record best-effort sender-side echo cleanup state")
    echo_delete.add_argument("--correlation-id")
    echo_delete.add_argument("--message-id")
    echo_delete.set_defaults(func=command_echo_delete)
