#!/usr/bin/env python3
"""Agent session CLI commands."""

from __future__ import annotations

import argparse
import json

from agent_user_status.session_registry import (
    append_session_event,
    append_session_heartbeat,
    session_summaries,
    session_timeline,
)
from agent_user_status.session_scan import scan_agent_sessions


def _session_metadata(args: argparse.Namespace) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "pid": args.pid,
            "cwd": args.cwd,
            "repo": args.repo,
            "tty": args.tty,
            "tmux_pane": args.tmux_pane,
        }.items()
        if value is not None
    }


def command_session_heartbeat(args: argparse.Namespace) -> int:
    record = append_session_heartbeat(
        args.session_id,
        agent_id=args.agent,
        status=args.status,
        state=args.state,
        note=args.note,
        metadata=_session_metadata(args),
        ttl_seconds=args.ttl_seconds,
    )
    print(json.dumps({"ok": True, "record": record}, indent=2))
    return 0


def command_session_event(args: argparse.Namespace) -> int:
    record = append_session_event(
        args.session_id,
        args.event_type,
        agent_id=args.agent,
        state=args.state,
        note=args.note,
        metadata=_session_metadata(args),
    )
    print(json.dumps({"ok": True, "record": record}, indent=2))
    return 0


def command_sessions(args: argparse.Namespace) -> int:
    if args.session_id:
        payload = {"ok": True, "records": session_timeline(args.session_id, limit=args.limit)}
    else:
        payload = {"ok": True, "sessions": session_summaries(limit=args.limit)}
    print(json.dumps(payload, indent=2))
    return 0


def command_session_scan(args: argparse.Namespace) -> int:
    payload = scan_agent_sessions(include_cwd=args.include_cwd)
    print(json.dumps({"ok": True, "scan": payload}, indent=2))
    return 0


def add_session_parsers(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    sessions = sub.add_parser("sessions", help="Inspect privacy-safe local agent sessions")
    sessions.add_argument("--session-id")
    sessions.add_argument("--limit", type=int, default=200)
    sessions.set_defaults(func=command_sessions)

    scan = sub.add_parser("session-scan", help="Scan local agent processes without raw args")
    scan.add_argument("--include-cwd", action="store_true", help="Include full cwd paths in local output")
    scan.set_defaults(func=command_session_scan)

    session_heartbeat = sub.add_parser("session-heartbeat", help="Record an agent session heartbeat")
    session_heartbeat.add_argument("--session-id", required=True)
    session_heartbeat.add_argument("--agent", default="agent")
    session_heartbeat.add_argument("--status", default="active")
    session_heartbeat.add_argument("--state")
    session_heartbeat.add_argument("--note")
    session_heartbeat.add_argument("--pid")
    session_heartbeat.add_argument("--cwd")
    session_heartbeat.add_argument("--repo")
    session_heartbeat.add_argument("--tty")
    session_heartbeat.add_argument("--tmux-pane")
    session_heartbeat.add_argument("--ttl-seconds", type=int, default=300)
    session_heartbeat.set_defaults(func=command_session_heartbeat)

    session_event = sub.add_parser("session-event", help="Record a privacy-safe agent session event")
    session_event.add_argument("--session-id", required=True)
    session_event.add_argument("--event-type", required=True)
    session_event.add_argument("--agent", default="agent")
    session_event.add_argument("--state")
    session_event.add_argument("--note")
    session_event.add_argument("--pid")
    session_event.add_argument("--cwd")
    session_event.add_argument("--repo")
    session_event.add_argument("--tty")
    session_event.add_argument("--tmux-pane")
    session_event.set_defaults(func=command_session_event)
