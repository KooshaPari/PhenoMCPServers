#!/usr/bin/env python3
"""MCP wrapper and manager for the local agent-imessage CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from agent_user_status.agent_imessage_core import RECIPIENT_ROLES, require_recipient_role
from agent_user_status.agent_imessage_mcp_comm import COMM_TOOL_NAMES, COMM_TOOLS, comm_tool_call
from agent_user_status.agent_imessage_mcp_install import (
    SERVER_NAME,
    call_agent_imessage,
    command_doctor,
    command_status,
)
from agent_user_status.agent_imessage_mcp_install import command_install as install_mcp_clients
from agent_user_status.agent_imessage_mcp_presence import (
    PRESENCE_TOOL_NAMES,
    PRESENCE_TOOLS,
    presence_tool_call,
)
from agent_user_status.agent_imessage_mcp_sessions import SESSION_TOOL_NAMES, SESSION_TOOLS, session_tool_call

UNREDACTED_STATUS_KEYS = {"latest_inbound_preview", "chat"}


def redact_agent_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)
    data = redacted.get("data")
    if isinstance(data, dict):
        data = dict(data)
        for key in UNREDACTED_STATUS_KEYS:
            data.pop(key, None)
        redacted["data"] = data
    return redacted


TOOLS: list[dict[str, Any]] = [
    {
        "name": "user_status",
        "description": "Estimate whether Koosha is likely to respond soon.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "hook_decision",
        "description": "Return a stop-hook decision frame for a candidate waiting message.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "notify_user",
        "description": "Send an iMessage/SMS notification to a scoped recipient role. Defaults to Koosha.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "recipient": {"type": "string", "enum": list(RECIPIENT_ROLES), "default": "koosha"},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    },
    *COMM_TOOLS,
    *PRESENCE_TOOLS,
    {
        "name": "wait_for_user_reply",
        "description": "Wait for the next inbound message from a scoped recipient role. Defaults to Koosha.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "recipient": {"type": "string", "enum": list(RECIPIENT_ROLES), "default": "koosha"},
                "timeout": {"type": "integer", "default": 900},
                "poll": {"type": "number", "default": 3.0},
                "include_existing": {"type": "boolean", "default": False},
            },
            "additionalProperties": False,
        },
    },
    *SESSION_TOOLS,
]


def tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name in SESSION_TOOL_NAMES:
        return session_tool_call(name, args, call_agent_imessage)
    if name in COMM_TOOL_NAMES:
        return comm_tool_call(name, args, call_agent_imessage)
    if name in PRESENCE_TOOL_NAMES:
        return presence_tool_call(name, args, call_agent_imessage)
    if name == "user_status":
        return redact_agent_payload(call_agent_imessage(["status", "--json"]))
    if name == "hook_decision":
        return call_agent_imessage(["hook-decision", "--text", str(args["text"])])
    if name == "notify_user":
        recipient = require_recipient_role(args.get("recipient"))
        command = ["notify", "--recipient", recipient, str(args["message"])]
        if args.get("dry_run"):
            command.append("--dry-run")
        return call_agent_imessage(command)
    if name == "wait_for_user_reply":
        recipient = require_recipient_role(args.get("recipient"))
        command = [
            "wait",
            "--recipient",
            recipient,
            "--timeout",
            str(args.get("timeout", 900)),
            "--poll",
            str(args.get("poll", 3.0)),
            "--json",
        ]
        if args.get("include_existing"):
            command.append("--include-existing")
        return call_agent_imessage(command, timeout=int(args.get("timeout", 900)) + 20)
    raise ValueError(f"Unknown tool: {name}")


def send_response(request_id: Any, result: dict[str, Any] | None = None, error: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        payload["error"] = error
    else:
        payload["result"] = result or {}
    print(json.dumps(payload), flush=True)


def mcp_serve() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            method = request.get("method")
            request_id = request.get("id")

            if method == "initialize":
                send_response(
                    request_id,
                    {
                        "protocolVersion": request.get("params", {}).get("protocolVersion", "2024-11-05"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": SERVER_NAME, "version": "0.1.0"},
                    },
                )
            elif method == "tools/list":
                send_response(request_id, {"tools": TOOLS})
            elif method == "tools/call":
                params = request.get("params", {})
                result = tool_call(str(params.get("name")), params.get("arguments") or {})
                send_response(
                    request_id,
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2),
                            }
                        ],
                        "isError": not result.get("ok", False),
                    },
                )
            elif method and method.startswith("notifications/"):
                continue
            else:
                send_response(request_id, error={"code": -32601, "message": f"Method not found: {method}"})
        except Exception as exc:
            request_id = locals().get("request", {}).get("id")
            send_response(request_id, error={"code": -32603, "message": str(exc)})
    return 0


def command_install(args: argparse.Namespace) -> int:
    return install_mcp_clients(args, Path(__file__).resolve())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MCP server and manager for agent-imessage")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the stdio MCP server")
    serve.set_defaults(func=lambda _args: mcp_serve())

    install = sub.add_parser("install", help="Register the CLI-backed MCP server")
    install.add_argument("--client", choices=["codex", "claude", "both"], default="both")
    install.add_argument(
        "--with-messages",
        action="store_true",
        help="Also repair the direct mac_messages_mcp registration",
    )
    install.set_defaults(func=command_install)

    status = sub.add_parser("status", help="Show MCP and user-status state")
    status.set_defaults(func=command_status)

    doctor = sub.add_parser("doctor", help="Run basic diagnostics")
    doctor.set_defaults(func=command_doctor)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
