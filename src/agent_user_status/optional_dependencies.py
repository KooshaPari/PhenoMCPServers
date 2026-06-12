"""Optional-dependency probes and soft-fail helpers for agent-imessage.

Every code path that touches iMessage/MCP/BlueBubbles SHOULD go through one
of the helpers in this module. When the dependency is missing, the helper
returns the same JSON shape that the success path would, but with
``ok=False`` and ``error="<dep>_unavailable"`` — callers can then
"skip + log" instead of raising.

This is what makes imessage *optional* end-to-end: a user with imessage
disabled in settings.json, or a fresh install with no Mac/iMessage account,
or a Linux/Windows host, gets graceful no-ops instead of tracebacks.

The probes are intentionally cheap (stat/exists checks, no subprocess
calls) so they can run on the hot path of the rust stop-hook binary.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

# Settings path for the imessage plugin toggle. If this file is missing or
# doesn't mention imessage at all, we default to "off" (safer).
CLAUDE_SETTINGS_PATH = Path(
    os.environ.get("CLAUDE_SETTINGS_PATH", "~/.claude/settings.json")
).expanduser()

# Binary paths — checked via shutil.which / Path.exists.
IMESSAGE_BIN_CANDIDATES = (
    Path("~/.local/bin/agent-imessage").expanduser(),
    Path("~/.local/bin/agent-imessage-mcp").expanduser(),
)

# BlueBubbles webhook sink — what feeds inbound read-receipts and replies.
BLUEBUBBLES_INBOUND_PATH = Path(
    os.environ.get("PHENOTYPE_IMESSAGE_INBOUND", "~/.phenotype/imessage-inbound.jsonl")
).expanduser()

# Where the iMessage plugin config lives. Plugin is "enabled" when its entry
# maps to a truthy value in settings.json.
IMESSAGE_PLUGIN_KEY = "imessage@claude-plugins-official"

# Cache the result of the heavy probe so the rust stop-hook binary can do
# sub-millisecond subsequent checks. Invalidated by mtime on settings.json.
_probe_cache: dict[str, Any] = {}


def _read_settings() -> dict[str, Any]:
    try:
        if not CLAUDE_SETTINGS_PATH.exists():
            return {}
        mtime = CLAUDE_SETTINGS_PATH.stat().st_mtime
        cached = _probe_cache.get("settings")
        if cached and cached.get("mtime") == mtime:
            return cached.get("data", {})
        with CLAUDE_SETTINGS_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        _probe_cache["settings"] = {"mtime": mtime, "data": data}
        return data
    except (OSError, json.JSONDecodeError):
        return {}


def is_plugin_enabled(plugin_key: str = IMESSAGE_PLUGIN_KEY) -> bool:
    """Return True only if the plugin is explicitly enabled in settings."""
    settings = _read_settings()
    plugins = settings.get("enabledPlugins", {})
    value = plugins.get(plugin_key)
    return bool(value) and value is not False


def is_imessage_available() -> bool:
    """Fast check: binary present AND plugin enabled (or not configured to off).

    Order matters: if the binary is missing, the answer is always False,
    regardless of settings. If the binary is present but settings disable
    the plugin, also False. If both are present and unset/on, True.
    """
    bin_present = any(p.exists() for p in IMESSAGE_BIN_CANDIDATES) or shutil.which(
        "agent-imessage"
    ) is not None
    if not bin_present:
        return False
    settings = _read_settings()
    if "enabledPlugins" not in settings:
        # No explicit config = treat as off (safer default)
        return False
    return is_plugin_enabled()


def is_bluebubbles_available() -> bool:
    """True if the BlueBubbles webhook sink file is writable.

    The sink is created lazily by the webhook receiver on first message,
    so we also accept "the parent dir exists and is writable" as available.
    """
    sink = BLUEBUBBLES_INBOUND_PATH
    if sink.exists():
        return True
    parent = sink.parent
    return parent.exists() and os.access(parent, os.W_OK)


def is_mcp_plugin_running() -> bool:
    """True if an `agent-imessage-mcp serve` process is running.

    Used by the lockfile daemon: if the MCP server is up, don't spawn
    another. Cheap: just checks `pgrep` exit code.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-f", "agent-imessage-mcp serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1.0,
            check=False,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def call_or_skip(
    cmd: list[str],
    *,
    timeout: float = 2.0,
    unavailable: str = "imessage_unavailable",
    unavailable_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a shell command, or return a uniform "unavailable" payload.

    Use this wrapper anywhere the previous code did ``subprocess.run(...)``
    against imessage. If imessage isn't available, the wrapper returns
    ``{"ok": False, "error": "<unavailable>"}`` immediately and never
    spawns a process — preserving the previous fast-fail behavior.
    """
    if not is_imessage_available():
        payload = {"ok": False, "error": unavailable}
        if unavailable_payload:
            payload.update(unavailable_payload)
        return payload
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            check=False,
            text=True,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{unavailable}_timeout", "timeout": timeout}
    except OSError as exc:
        return {"ok": False, "error": f"{unavailable}_oserror", "detail": str(exc)}
    if result.returncode != 0:
        return {
            "ok": False,
            "error": f"{unavailable}_nonzero_exit",
            "exit": result.returncode,
            "stderr": (result.stderr or "")[:512],
        }
    try:
        return {"ok": True, "stdout": result.stdout, "parsed": json.loads(result.stdout)}
    except json.JSONDecodeError:
        return {"ok": True, "stdout": result.stdout, "parsed": None}


def drain_inbound(
    since_iso: str | None = None,
    *,
    kinds: tuple[str, ...] = ("read_receipt", "reply", "tapback"),
) -> list[dict[str, Any]]:
    """Return inbound events from the BlueBubbles webhook sink.

    Used by the new ``read-receipts`` and ``user-responses`` subcommands to
    surface iMessage reactions for Codex/CC hooks. Returns an empty list
    (not an error) when imessage/bluebubbles is unavailable.
    """
    if not is_imessage_available() and not is_bluebubbles_available():
        return []
    if not BLUEBUBBLES_INBOUND_PATH.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        with BLUEBUBBLES_INBOUND_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kind = rec.get("type") or rec.get("data", {}).get("type")
                if kinds and kind not in kinds:
                    continue
                if since_iso and rec.get("received_at", "") < since_iso:
                    continue
                out.append(rec)
    except OSError:
        return []
    return out


__all__ = [
    "CLAUDE_SETTINGS_PATH",
    "IMESSAGE_PLUGIN_KEY",
    "BLUEBUBBLES_INBOUND_PATH",
    "is_imessage_available",
    "is_bluebubbles_available",
    "is_mcp_plugin_running",
    "is_plugin_enabled",
    "call_or_skip",
    "drain_inbound",
]
