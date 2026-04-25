#!/usr/bin/env python3
"""Agent session CLI commands."""

from __future__ import annotations

import argparse
import json

from agent_user_status.session_registry import (
    append_child_session_event,
    append_session_event,
    append_session_heartbeat,
    recent_session_events,
    session_snapshot,
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


def command_session_events(args: argparse.Namespace) -> int:
    payload = recent_session_events(limit=args.limit, kind=args.kind, session_id=args.session_id)
    print(json.dumps({"ok": True, "events": payload}, indent=2))
    return 0


def command_session_snapshot(args: argparse.Namespace) -> int:
    payload = session_snapshot(
        session_id=args.session_id,
        session_limit=args.session_limit,
        event_limit=args.event_limit,
        kind=args.kind,
    )
    print(json.dumps({"ok": True, "snapshot": payload}, indent=2))
    return 0


def command_session_child(args: argparse.Namespace) -> int:
    metadata = _session_metadata(args)
    if args.result is not None:
        metadata["result"] = args.result
    record = append_child_session_event(
        args.parent_session_id,
        args.child_session_id,
        args.lifecycle,
        agent_id=args.agent,
        child_agent_id=args.child_agent,
        state=args.state,
        note=args.note,
        metadata=metadata,
    )
    print(json.dumps({"ok": True, "record": record}, indent=2))
    return 0


def add_session_parsers(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    sessions = sub.add_parser("sessions", help="Inspect privacy-safe local agent sessions")
    sessions.add_argument("--session-id")
    sessions.add_argument("--limit", type=int, default=200)
    sessions.set_defaults(func=command_sessions)

    scan = sub.add_parser("session-scan", help="Scan local agent processes without raw args")
    scan.add_argument("--include-cwd", action="store_true", help="Include full cwd paths in local output")
    scan.set_defaults(func=command_session_scan)

    events = sub.add_parser("session-events", help="Inspect in-process session event ring")
    events.add_argument("--limit", type=int, default=80)
    events.add_argument("--kind", choices=["heartbeat", "event"])
    events.add_argument("--session-id")
    events.set_defaults(func=command_session_events)

    snapshot = sub.add_parser("session-snapshot", help="Inspect live session and event snapshot")
    snapshot.add_argument("--session-id")
    snapshot.add_argument("--session-limit", type=int, default=200)
    snapshot.add_argument("--event-limit", type=int, default=80)
    snapshot.add_argument("--kind", choices=["heartbeat", "event"])
    snapshot.set_defaults(func=command_session_snapshot)

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

    child_spawn = sub.add_parser("session-child-spawn", help="Record a child agent spawn event")
    child_spawn.add_argument("--parent-session-id", required=True)
    child_spawn.add_argument("--child-session-id", required=True)
    child_spawn.add_argument("--agent", default="agent")
    child_spawn.add_argument("--child-agent")
    child_spawn.add_argument("--state", default="spawned")
    child_spawn.add_argument("--note")
    child_spawn.add_argument("--pid")
    child_spawn.add_argument("--cwd")
    child_spawn.add_argument("--repo")
    child_spawn.add_argument("--tty")
    child_spawn.add_argument("--tmux-pane")
    child_spawn.set_defaults(func=command_session_child, lifecycle="spawn", result=None)

    child_close = sub.add_parser("session-child-close", help="Record a child agent close event")
    child_close.add_argument("--parent-session-id", required=True)
    child_close.add_argument("--child-session-id", required=True)
    child_close.add_argument("--agent", default="agent")
    child_close.add_argument("--child-agent")
    child_close.add_argument("--state", default="closed")
    child_close.add_argument("--result")
    child_close.add_argument("--note")
    child_close.add_argument("--pid")
    child_close.add_argument("--cwd")
    child_close.add_argument("--repo")
    child_close.add_argument("--tty")
    child_close.add_argument("--tmux-pane")
    child_close.set_defaults(func=command_session_child, lifecycle="close")
