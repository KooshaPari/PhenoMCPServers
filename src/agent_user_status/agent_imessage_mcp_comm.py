"""Structured communication tools for the agent-imessage MCP wrapper."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from agent_user_status.agent_imessage_core import RECIPIENT_ROLES, require_recipient_role

COMM_TOOL_NAMES = {"notify_user_structured", "parse_user_reply"}

COMM_TOOLS: list[dict[str, Any]] = [
    {
        "name": "notify_user_structured",
        "description": "Send a structured agent-to-user message envelope with task/session/project metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "recipient": {"type": "string", "enum": list(RECIPIENT_ROLES), "default": "koosha"},
                "sender_name": {"type": "string", "default": "codex"},
                "sender_kind": {"type": "string", "default": "codex"},
                "session_id": {"type": "string"},
                "task_id": {"type": "string"},
                "project": {"type": "string"},
                "repo_path": {"type": "string"},
                "urgency": {"type": "string", "enum": ["low", "normal", "high", "urgent"], "default": "normal"},
                "expires_minutes": {"type": "integer"},
                "correlation_id": {"type": "string"},
                "answer_schema_json": {"type": "string"},
                "dry_run": {"type": "boolean", "default": False},
            },
            "required": ["message"],
            "additionalProperties": False,
        },
    },
    {
        "name": "parse_user_reply",
        "description": "Parse a user reply such as A1 or A1,A3 against an elicitation schema.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "reply": {"type": "string"},
                "answer_schema_json": {"type": "string"},
            },
            "required": ["reply", "answer_schema_json"],
            "additionalProperties": False,
        },
    },
]


def comm_tool_call(
    name: str,
    args: dict[str, Any],
    call_agent_imessage: Callable[[list[str]], dict[str, Any]],
) -> dict[str, Any]:
    if name == "notify_user_structured":
        recipient = require_recipient_role(args.get("recipient"))
        command = ["notify-structured", "--recipient", recipient, str(args["message"])]
        option_map = {
            "sender_name": "--sender-name",
            "sender_kind": "--sender-kind",
            "session_id": "--session-id",
            "task_id": "--task-id",
            "project": "--project",
            "repo_path": "--repo-path",
            "urgency": "--urgency",
            "expires_minutes": "--expires-minutes",
            "correlation_id": "--correlation-id",
            "answer_schema_json": "--answer-schema-json",
        }
        for key, flag in option_map.items():
            if args.get(key) is not None:
                command.extend([flag, str(args[key])])
        if args.get("dry_run"):
            command.append("--dry-run")
        return call_agent_imessage(command)
    if name == "parse_user_reply":
        return call_agent_imessage(
            ["parse-reply", str(args["reply"]), "--answer-schema-json", str(args["answer_schema_json"])]
        )
    raise ValueError(f"Unknown structured communication tool: {name}")
