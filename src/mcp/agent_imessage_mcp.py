#!/usr/bin/env python3
"""MCP wrapper and manager for the local agent-imessage CLI."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from agent_user_status.agent_imessage_core import RECIPIENT_ROLES, require_recipient_role
from agent_user_status.bootstrap_support import agent_imessage_bin

AGENT_IMESSAGE = str(agent_imessage_bin())
SERVER_NAME = "agent-imessage"
MESSAGES_SERVER_ARGS = [
    "uvx",
    "--python",
    "3.11",
    "--from",
    "git+https://github.com/carterlasalle/mac_messages_mcp.git",
    "mac-messages-mcp",
]
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


def run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )


def call_agent_imessage(args: list[str], timeout: int = 60) -> dict[str, Any]:
    result = run([AGENT_IMESSAGE, *args], timeout=timeout)
    text = result.stdout.strip()
    try:
        parsed = json.loads(text) if text else {}
    except json.JSONDecodeError:
        parsed = {"text": text}
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "data": parsed,
    }


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
]


def tool_call(name: str, args: dict[str, Any]) -> dict[str, Any]:
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
    if name == "set_user_status":
        command = ["set-status", str(args["mode"])]
        if args.get("minutes") is not None:
            command.extend(["--minutes", str(args["minutes"])])
        if args.get("eta_minutes") is not None:
            command.extend(["--eta-minutes", str(args["eta_minutes"])])
        if args.get("confidence") is not None:
            command.extend(["--confidence", str(args["confidence"])])
        if args.get("note"):
            command.extend(["--note", str(args["note"])])
        return call_agent_imessage(command)
    if name == "clear_user_status":
        return call_agent_imessage(["clear-status"])
    if name == "record_presence_signal":
        command = ["signal", str(args["name"]), "--score", str(args["score"])]
        if args.get("state"):
            command.extend(["--state", str(args["state"])])
        if args.get("weight") is not None:
            command.extend(["--weight", str(args["weight"])])
        if args.get("eta_minutes") is not None:
            command.extend(["--eta-minutes", str(args["eta_minutes"])])
        if args.get("max_age_seconds") is not None:
            command.extend(["--max-age-seconds", str(args["max_age_seconds"])])
        if args.get("note"):
            command.extend(["--note", str(args["note"])])
        return call_agent_imessage(command)
    if name == "inspect_presence_signals":
        return call_agent_imessage(["signals"])
    if name == "record_user_action":
        command = ["action", str(args["direction"]), str(args["kind"])]
        if args.get("score") is not None:
            command.extend(["--score", str(args["score"])])
        if args.get("weight") is not None:
            command.extend(["--weight", str(args["weight"])])
        if args.get("state"):
            command.extend(["--state", str(args["state"])])
        if args.get("eta_minutes") is not None:
            command.extend(["--eta-minutes", str(args["eta_minutes"])])
        if args.get("max_age_seconds") is not None:
            command.extend(["--max-age-seconds", str(args["max_age_seconds"])])
        if args.get("note"):
            command.extend(["--note", str(args["note"])])
        return call_agent_imessage(command)
    if name == "inspect_user_actions":
        return call_agent_imessage(["actions"])
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


def install_codex() -> dict[str, Any]:
    run(["codex", "mcp", "remove", SERVER_NAME], timeout=30)
    result = run(["codex", "mcp", "add", SERVER_NAME, "--", str(Path(__file__).resolve()), "serve"], timeout=30)
    return {"client": "codex", "ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}


def install_claude() -> dict[str, Any]:
    run(["claude", "mcp", "remove", SERVER_NAME, "-s", "user"], timeout=30)
    result = run(
        ["claude", "mcp", "add", "-s", "user", SERVER_NAME, "--", str(Path(__file__).resolve()), "serve"],
        timeout=30,
    )
    return {"client": "claude", "ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}


def install_messages_mcp(client: str) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    if client in {"codex", "both"}:
        run(["codex", "mcp", "remove", "messages"], timeout=30)
        result = run(["codex", "mcp", "add", "messages", "--", *MESSAGES_SERVER_ARGS], timeout=30)
        results.append(
            {"client": "codex", "ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}
        )
    if client in {"claude", "both"}:
        run(["claude", "mcp", "remove", "messages", "-s", "user"], timeout=30)
        result = run(["claude", "mcp", "add", "-s", "user", "messages", "--", *MESSAGES_SERVER_ARGS], timeout=30)
        results.append(
            {"client": "claude", "ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}
        )
    return {"messages_mcp": results}


def command_install(args: argparse.Namespace) -> int:
    if args.with_messages and os.environ.get("AGENT_IMESSAGE_ALLOW_GENERIC_MESSAGES_MCP") != "1":
        raise SystemExit(
            "--with-messages registers a generic Messages MCP and is disabled by default. "
            "Set AGENT_IMESSAGE_ALLOW_GENERIC_MESSAGES_MCP=1 only for explicit local admin repair."
        )

    results: list[dict[str, Any]] = []
    if args.client in {"codex", "both"}:
        results.append(install_codex())
    if args.client in {"claude", "both"}:
        results.append(install_claude())
    if args.with_messages:
        results.append(install_messages_mcp(args.client))
    print(json.dumps({"ok": all(r.get("ok", True) for r in results), "results": results}, indent=2))
    return 0


def command_status(args: argparse.Namespace) -> int:
    payload = {
        "agent_imessage": call_agent_imessage(["status", "--json"]),
        "codex": run(["codex", "mcp", "get", SERVER_NAME], timeout=30).stdout,
        "claude": run(["claude", "mcp", "get", SERVER_NAME], timeout=30).stdout,
        "messages_codex": run(["codex", "mcp", "get", "messages"], timeout=30).stdout,
        "messages_claude": run(["claude", "mcp", "get", "messages"], timeout=30).stdout,
    }
    print(json.dumps(payload, indent=2))
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []
    for binary in ["codex", "claude", "uvx", "agent-imessage"]:
        result = run(["/bin/zsh", "-lc", f"command -v {binary}"], timeout=10)
        checks.append({"check": f"binary:{binary}", "ok": result.returncode == 0, "path": result.stdout.strip()})
    checks.append({"check": "agent-status", **call_agent_imessage(["status", "--json"])})
    codex = run(["codex", "mcp", "get", SERVER_NAME], timeout=30)
    claude = run(["claude", "mcp", "get", SERVER_NAME], timeout=30)
    checks.append(
        {
            "check": "codex-agent-imessage-mcp",
            "ok": codex.returncode == 0,
            "stdout": codex.stdout,
            "stderr": codex.stderr,
        }
    )
    checks.append(
        {
            "check": "claude-agent-imessage-mcp",
            "ok": claude.returncode == 0,
            "stdout": claude.stdout,
            "stderr": claude.stderr,
        }
    )
    print(json.dumps({"ok": all(item.get("ok", False) for item in checks), "checks": checks}, indent=2))
    return 0


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
