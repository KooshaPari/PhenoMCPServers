#!/usr/bin/env python3
"""Local persistent backend for derived user-status signals.

This service intentionally accepts only abstracted state. Eye tracking or camera
observers should reduce data locally and send short-lived scores/regions, never
frames, images, landmarks, face embeddings, or raw gaze streams.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from agent_user_status.bootstrap_support import agent_imessage_bin
from agent_user_status.correction import recent_correction_events, store_correction_event
from agent_user_status.eye_state_payload import bounded_int
from agent_user_status.gaze_context import as_bool
from agent_user_status.monitor_html import MONITOR_HTML
from agent_user_status.state_retention import delete_state, export_state, retain_recent_state
from agent_user_status.statusd_command_cache import cached_command_result, clear_command_cache
from agent_user_status.statusd_commands import build_action_command, build_signal_command
from agent_user_status.statusd_eye import dev_state as build_dev_state
from agent_user_status.statusd_eye import store_eye_payload as persist_eye_payload
from agent_user_status.statusd_privacy import MAX_BODY_BYTES, PRIVACY_POLICY, reject_raw_payload
from agent_user_status.statusd_sessions import parsed_query, session_get_payload, session_post_payload

HOST = os.environ.get("AGENT_USER_STATUSD_HOST", "127.0.0.1")
PORT = int(os.environ.get("AGENT_USER_STATUSD_PORT", "8765"))
AGENT_IMESSAGE = str(agent_imessage_bin())
STATE_DIR = Path(os.environ.get("AGENT_IMESSAGE_STATE_DIR", "~/.local/share/agent-imessage/state")).expanduser()
DEV_STATE_PATH = STATE_DIR / "dev_monitor_state.json"


def run_agent(args: list[str], timeout: int = 30) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [AGENT_IMESSAGE, *args],
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "returncode": 124, "data": {}, "stderr": f"agent-imessage timed out after {timeout}s"}
    except OSError as exc:
        return {"ok": False, "returncode": 127, "data": {}, "stderr": str(exc)}
    try:
        data = json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        data = {"text": result.stdout}
    return {"ok": result.returncode == 0, "returncode": result.returncode, "data": data, "stderr": result.stderr}


def redacted_agent(args: list[str], timeout: int = 30) -> dict[str, Any]:
    result = run_agent(args, timeout=timeout)
    data = result.get("data")
    if isinstance(data, dict):
        data.pop("latest_inbound_preview", None)
        data.pop("chat", None)
    return result


def dev_state() -> dict[str, Any]:
    return build_dev_state(DEV_STATE_PATH)


def store_eye_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return persist_eye_payload(payload, STATE_DIR, DEV_STATE_PATH, run_agent)


class Handler(BaseHTTPRequestHandler):
    server_version = "agent-user-statusd/0.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # HTTP clients may disconnect after receiving enough local status data.
            pass

    def send_html(self, status: int, body_text: str) -> None:
        body = body_text.encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            # Browser monitor refreshes can close the socket before the body flushes.
            pass

    def send_sse(self, payloads: list[dict[str, Any]]) -> None:
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            for payload in payloads:
                body = json.dumps(payload, sort_keys=True)
                self.wfile.write(f"event: session\ndata: {body}\n\n".encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # SSE listeners are optional and may disconnect between session events.
            pass

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > MAX_BODY_BYTES:
            raise ValueError("payload too large")
        body = self.rfile.read(length) if length else b"{}"
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")
        return payload

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/health":
                self.send_json(200, {"ok": True, "service": "agent-user-statusd"})
            elif path == "/monitor":
                self.send_html(200, MONITOR_HTML)
            elif path == "/privacy":
                self.send_json(200, {"ok": True, "policy": PRIVACY_POLICY})
            elif path == "/state/export":
                self.send_json(200, {"ok": True, "export": export_state(STATE_DIR)})
            elif path == "/dev/state":
                self.send_json(200, {"ok": True, **dev_state()})
            elif path == "/dev/eye":
                if parse_qs(parsed.query):
                    self.send_json(405, {"ok": False, "error": "use POST /dev/eye to update eye state"})
                else:
                    self.send_json(200, {"ok": True, **dev_state()})
            elif path == "/status":
                result = cached_command_result("status-json", lambda: redacted_agent(["status", "--json"], timeout=4))
                self.send_json(200 if result.get("ok") else 502, result)
            elif path == "/signals":
                result = cached_command_result("signals", lambda: run_agent(["signals"], timeout=4))
                self.send_json(200 if result.get("ok") else 502, result)
            elif path == "/actions":
                result = cached_command_result("actions", lambda: run_agent(["actions"], timeout=4))
                self.send_json(200 if result.get("ok") else 502, result)
            elif path == "/events/stream":
                query = parse_qs(parsed.query)
                limit = bounded_int(query.get("limit", [80])[0], 80, 1, 500, "limit")
                session_payload = session_get_payload(
                    "/session/snapshot",
                    {"event_limit": [str(limit)], "session_limit": [str(limit)]},
                )
                self.send_sse([session_payload or {"ok": True, "snapshot": {}}])
            elif session_payload := session_get_payload(path, parsed_query(parsed.query)):
                self.send_json(200, session_payload)
            elif path == "/correction/events":
                query = parse_qs(parsed.query)
                limit = bounded_int(query.get("limit", [80])[0], 80, 1, 500, "limit")
                reliable_only = as_bool(query.get("reliable_only", ["false"])[0], False)
                self.send_json(
                    200,
                    {"ok": True, "events": recent_correction_events(limit, reliable_only=reliable_only)},
                )
            else:
                self.send_json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
            rejection = reject_raw_payload(payload)
            if rejection:
                self.send_json(422, {"ok": False, "error": rejection, "policy": PRIVACY_POLICY})
                return

            if path == "/signal":
                result = run_agent(build_signal_command(payload), timeout=4)
                if result.get("ok"):
                    clear_command_cache()
                self.send_json(200 if result.get("ok") else 502, result)
            elif path == "/dev/eye":
                self.send_json(200, {"ok": True, **store_eye_payload(payload)})
            elif path == "/correction/event":
                self.send_json(200, {"ok": True, "event": store_correction_event(payload)})
            elif session_payload := session_post_payload(path, payload):
                self.send_json(200, session_payload)
            elif path == "/state/delete":
                names = payload.get("names")
                selected = [str(name) for name in names] if isinstance(names, list) else None
                self.send_json(200, {"ok": True, **delete_state(STATE_DIR, names=selected)})
            elif path == "/state/retention":
                max_age = bounded_int(payload.get("max_age_seconds"), 86400, 1, 31_536_000, "max_age_seconds")
                self.send_json(200, {"ok": True, **retain_recent_state(STATE_DIR, max_age_seconds=max_age)})
            elif path == "/action":
                result = run_agent(build_action_command(payload), timeout=4)
                if result.get("ok"):
                    clear_command_cache()
                self.send_json(200 if result.get("ok") else 502, result)
            else:
                self.send_json(404, {"ok": False, "error": "not found"})
        except Exception as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})


def command_serve(args: argparse.Namespace) -> int:
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"ok": True, "listen": f"http://{args.host}:{args.port}"}, indent=2), flush=True)
    server.serve_forever()
    return 0


def command_health(args: argparse.Namespace) -> int:
    import urllib.request

    with urllib.request.urlopen(f"http://{args.host}:{args.port}/health", timeout=5) as response:
        print(response.read().decode("utf-8"))
    return 0


def command_open_monitor(args: argparse.Namespace) -> int:
    subprocess.run(["open", f"http://{args.host}:{args.port}/monitor"], check=False)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Persistent local backend for derived user-status signals")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Run the local HTTP backend")
    serve.add_argument("--host", default=HOST)
    serve.add_argument("--port", type=int, default=PORT)
    serve.set_defaults(func=command_serve)

    health = sub.add_parser("health", help="Check a running backend")
    health.add_argument("--host", default=HOST)
    health.add_argument("--port", type=int, default=PORT)
    health.set_defaults(func=command_health)

    monitor = sub.add_parser("open-monitor", help="Open the local dev monitor UI")
    monitor.add_argument("--host", default=HOST)
    monitor.add_argument("--port", type=int, default=PORT)
    monitor.set_defaults(func=command_open_monitor)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
