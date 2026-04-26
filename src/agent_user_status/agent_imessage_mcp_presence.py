#!/usr/bin/env python3
"""Presence MCP tool schemas and dispatch helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

PRESENCE_TOOL_NAMES = {
    "set_user_status",
    "clear_user_status",
    "record_presence_signal",
    "inspect_presence_signals",
    "record_user_action",
    "inspect_user_actions",
}

PRESENCE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "set_user_status",
        "description": "Set a manual response-likelihood override.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["active", "near", "away", "focus", "sleep", "async", "unknown"],
                },
                "minutes": {"type": "integer", "default": 60},
                "eta_minutes": {"type": "integer"},
                "confidence": {"type": "number"},
                "note": {"type": "string"},
            },
            "required": ["mode"],
            "additionalProperties": False,
        },
    },
    {
        "name": "clear_user_status",
        "description": "Clear the manual response-likelihood override.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "record_presence_signal",
        "description": "Record a short-lived external signal such as eye tracking or process tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "score": {"type": "number"},
                "state": {"type": "string"},
                "weight": {"type": "number", "default": 1.0},
                "eta_minutes": {"type": "integer"},
                "max_age_seconds": {"type": "integer", "default": 300},
                "note": {"type": "string"},
            },
            "required": ["name", "score"],
            "additionalProperties": False,
        },
    },
    {
        "name": "inspect_presence_signals",
        "description": "Inspect built-in, external, and learned response-likelihood signals.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "record_user_action",
        "description": "Record a local input/output action such as mouse_click, key_press, or video_playing.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["input", "output"]},
                "kind": {"type": "string"},
                "score": {"type": "number"},
                "weight": {"type": "number", "default": 1.0},
                "state": {"type": "string"},
                "eta_minutes": {"type": "integer"},
                "max_age_seconds": {"type": "integer", "default": 180},
                "note": {"type": "string"},
            },
            "required": ["direction", "kind"],
            "additionalProperties": False,
        },
    },
    {
        "name": "inspect_user_actions",
        "description": "Inspect recent input/output actions and per-action response learning.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def _add_optional(command: list[str], args: dict[str, Any], key: str, flag: str) -> None:
    value = args.get(key)
    if value is not None:
        command.extend([flag, str(value)])


def presence_tool_call(
    name: str,
    args: dict[str, Any],
    call_agent_imessage: Callable[[list[str]], dict[str, Any]],
) -> dict[str, Any]:
    if name == "set_user_status":
        command = ["set-status", str(args["mode"])]
        _add_optional(command, args, "minutes", "--minutes")
        _add_optional(command, args, "eta_minutes", "--eta-minutes")
        _add_optional(command, args, "confidence", "--confidence")
        if args.get("note"):
            command.extend(["--note", str(args["note"])])
        return call_agent_imessage(command)

    if name == "clear_user_status":
        return call_agent_imessage(["clear-status"])

    if name == "record_presence_signal":
        command = ["signal", str(args["name"]), "--score", str(args["score"])]
        if args.get("state"):
            command.extend(["--state", str(args["state"])])
        _add_optional(command, args, "weight", "--weight")
        _add_optional(command, args, "eta_minutes", "--eta-minutes")
        _add_optional(command, args, "max_age_seconds", "--max-age-seconds")
        if args.get("note"):
            command.extend(["--note", str(args["note"])])
        return call_agent_imessage(command)

    if name == "inspect_presence_signals":
        return call_agent_imessage(["signals"])

    if name == "record_user_action":
        command = ["action", str(args["direction"]), str(args["kind"])]
        _add_optional(command, args, "score", "--score")
        _add_optional(command, args, "weight", "--weight")
        if args.get("state"):
            command.extend(["--state", str(args["state"])])
        _add_optional(command, args, "eta_minutes", "--eta-minutes")
        _add_optional(command, args, "max_age_seconds", "--max-age-seconds")
        if args.get("note"):
            command.extend(["--note", str(args["note"])])
        return call_agent_imessage(command)

    if name == "inspect_user_actions":
        return call_agent_imessage(["actions"])

    raise ValueError(f"Unknown presence tool: {name}")
