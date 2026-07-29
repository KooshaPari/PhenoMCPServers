#!/usr/bin/env python3
"""Session MCP tool schemas and dispatch helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_user_status.optional_dependencies import is_imessage_available

SESSION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "sessions",
        "description": "Inspect privacy-safe local agent session summaries or one session timeline.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "limit": {"type": "integer", "default": 200},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "session_heartbeat",
        "description": "Record a short-lived privacy-safe session heartbeat.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "agent": {"type": "string", "default": "agent"},
                "status": {"type": "string", "default": "active"},
                "state": {"type": "string"},
                "note": {"type": "string"},
                "ttl_seconds": {"type": "integer", "default": 300},
                "pid": {"type": "string"},
                "cwd": {"type": "string"},
                "repo": {"type": "string"},
                "tty": {"type": "string"},
                "tmux_pane": {"type": "string"},
            },
            "required": ["session_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "session_event",
        "description": "Record a privacy-safe abstract session event.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "event_type": {"type": "string"},
                "agent": {"type": "string", "default": "agent"},
                "state": {"type": "string"},
                "note": {"type": "string"},
                "pid": {"type": "string"},
                "cwd": {"type": "string"},
                "repo": {"type": "string"},
                "tty": {"type": "string"},
                "tmux_pane": {"type": "string"},
            },
            "required": ["session_id", "event_type"],
            "additionalProperties": False,
        },
    },
    {
        "name": "session_scan",
        "description": "Scan local agent processes and tmux panes without raw command args.",
        "inputSchema": {
            "type": "object",
            "properties": {"include_cwd": {"type": "boolean", "default": False}},
            "additionalProperties": False,
        },
    },
    {
        "name": "session_events",
        "description": "Inspect recent session heartbeat/event records.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 80},
                "kind": {"type": "string", "enum": ["heartbeat", "event"]},
                "session_id": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "poll_user_response",
        "description": (
            "Drain BlueBubbles reply/tapback events newer than ``since``"
            " (empty list when imessage is unavailable)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "since": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 5},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "poll_read_receipts",
        "description": (
            "Drain BlueBubbles read-receipt events newer than ``since``"
            " (empty list when imessage is unavailable)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "since": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 5},
            },
            "additionalProperties": False,
        },
    },
]

SESSION_TOOL_NAMES = {tool["name"] for tool in SESSION_TOOLS}


def _add_optional(command: list[str], args: dict[str, Any], name: str, flag: str | None = None) -> None:
    value = args.get(name)
    if value is not None:
        command.extend([flag or f"--{name.replace('_', '-')}", str(value)])


def session_tool_call(
    name: str,
    args: dict[str, Any],
    call_agent_imessage: Callable[[list[str]], dict[str, Any]],
) -> dict[str, Any]:
    if name == "sessions":
        command = ["sessions", "--limit", str(args.get("limit", 200))]
        _add_optional(command, args, "session_id")
        return call_agent_imessage(command)

    if name == "session_heartbeat":
        command = [
            "session-heartbeat",
            "--session-id",
            str(args["session_id"]),
            "--agent",
            str(args.get("agent", "agent")),
            "--status",
            str(args.get("status", "active")),
            "--ttl-seconds",
            str(args.get("ttl_seconds", 300)),
        ]
        for key in ["state", "note", "pid", "cwd", "repo", "tty", "tmux_pane"]:
            _add_optional(command, args, key)
        return call_agent_imessage(command)

    if name == "session_event":
        command = [
            "session-event",
            "--session-id",
            str(args["session_id"]),
            "--event-type",
            str(args["event_type"]),
            "--agent",
            str(args.get("agent", "agent")),
        ]
        for key in ["state", "note", "pid", "cwd", "repo", "tty", "tmux_pane"]:
            _add_optional(command, args, key)
        return call_agent_imessage(command)

    if name == "session_scan":
        command = ["session-scan"]
        if args.get("include_cwd"):
            command.append("--include-cwd")
        return call_agent_imessage(command)

    if name == "session_events":
        command = ["session-events", "--limit", str(args.get("limit", 80))]
        _add_optional(command, args, "kind")
        _add_optional(command, args, "session_id")
        return call_agent_imessage(command)

    if name == "poll_user_response":
        if not is_imessage_available():
            return {"ok": True, "events": []}
        command = ["user-responses"]
        _add_optional(command, args, "since")
        return call_agent_imessage(command)

    if name == "poll_read_receipts":
        if not is_imessage_available():
            return {"ok": True, "events": []}
        command = ["read-receipts"]
        _add_optional(command, args, "since")
        return call_agent_imessage(command)

    raise ValueError(f"Unknown session tool: {name}")
