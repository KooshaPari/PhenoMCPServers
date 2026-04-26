"""Install and diagnostics helpers for the agent-imessage MCP wrapper."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

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


def run(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        capture_output=True,
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


def install_codex(server_path: Path) -> dict[str, Any]:
    run(["codex", "mcp", "remove", SERVER_NAME], timeout=30)
    result = run(["codex", "mcp", "add", SERVER_NAME, "--", str(server_path), "serve"], timeout=30)
    return {"client": "codex", "ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}


def install_claude(server_path: Path) -> dict[str, Any]:
    run(["claude", "mcp", "remove", SERVER_NAME, "-s", "user"], timeout=30)
    result = run(
        ["claude", "mcp", "add", "-s", "user", SERVER_NAME, "--", str(server_path), "serve"],
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


def command_install(args: argparse.Namespace, server_path: Path) -> int:
    if args.with_messages and os.environ.get("AGENT_IMESSAGE_ALLOW_GENERIC_MESSAGES_MCP") != "1":
        raise SystemExit(
            "--with-messages registers a generic Messages MCP and is disabled by default. "
            "Set AGENT_IMESSAGE_ALLOW_GENERIC_MESSAGES_MCP=1 only for explicit local admin repair."
        )

    results: list[dict[str, Any]] = []
    if args.client in {"codex", "both"}:
        results.append(install_codex(server_path))
    if args.client in {"claude", "both"}:
        results.append(install_claude(server_path))
    if args.with_messages:
        results.append(install_messages_mcp(args.client))
    print(json.dumps({"ok": all(r.get("ok", True) for r in results), "results": results}, indent=2))
    return 0


def command_status(_args: argparse.Namespace) -> int:
    payload = {
        "agent_imessage": call_agent_imessage(["status", "--json"]),
        "codex": run(["codex", "mcp", "get", SERVER_NAME], timeout=30).stdout,
        "claude": run(["claude", "mcp", "get", SERVER_NAME], timeout=30).stdout,
        "messages_codex": run(["codex", "mcp", "get", "messages"], timeout=30).stdout,
        "messages_claude": run(["claude", "mcp", "get", "messages"], timeout=30).stdout,
    }
    print(json.dumps(payload, indent=2))
    return 0


def command_doctor(_args: argparse.Namespace) -> int:
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
