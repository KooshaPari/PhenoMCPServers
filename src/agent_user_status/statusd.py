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
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from agent_user_status.bootstrap_support import agent_imessage_bin
from agent_user_status.correction import recent_correction_events, store_correction_event
from agent_user_status.gaze_context import as_bool
from agent_user_status.gaze_drift_correction import load_drift_correction
from agent_user_status.eye_state_payload import bounded_float, bounded_int, build_eye_record, now_iso
from agent_user_status.monitor_html import MONITOR_HTML

HOST = os.environ.get("AGENT_USER_STATUSD_HOST", "127.0.0.1")
PORT = int(os.environ.get("AGENT_USER_STATUSD_PORT", "8765"))
AGENT_IMESSAGE = str(agent_imessage_bin())
STATE_DIR = Path(os.environ.get("AGENT_IMESSAGE_STATE_DIR", "~/.local/share/agent-imessage/state")).expanduser()
DEV_STATE_PATH = STATE_DIR / "dev_monitor_state.json"
MAX_BODY_BYTES = 16_384
EYE_SIGNAL_INTERVAL_SECONDS = float(os.environ.get("AGENT_USER_STATUSD_EYE_SIGNAL_INTERVAL_SECONDS", "1.0"))
RAW_SENSOR_PATTERNS = re.compile(
    r"(^|[^a-z0-9])(raw|frame|image|photo|screenshot|face|facial|biometric|"
    r"pupil|retina|iris|embedding|landmark|camera|webcam|transcript|waveform|"
    r"typed_text|key_name|keystroke|keycode)($|[^a-z0-9])",
    re.IGNORECASE,
)


PRIVACY_POLICY = {
    "classification": "highly_confidential_derived_presence",
    "retention": "short_lived_signals_only; agent-imessage max_age_seconds gates freshness",
    "accepted": [
        "score",
        "state",
        "screen_zone",
        "bounded screen coordinates for explicit correction events",
        "confidence",
        "eta_minutes",
        "max_age_seconds",
        "short note without raw sensor content",
    ],
    "rejected": [
        "camera frames",
        "screenshots",
        "face or eye images",
        "facial landmarks",
        "biometric embeddings",
        "raw gaze streams",
        "medical inference labels",
        "keystroke contents or key names",
        "audio transcripts or waveforms",
    ],
}

_EYE_SIGNAL_LOCK = threading.Lock()
_EYE_SIGNAL_WORKER_RUNNING = False
_EYE_SIGNAL_PENDING: dict[str, Any] | None = None
_EYE_SIGNAL_LAST_DISPATCH = 0.0


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


def queue_eye_signal(state: str, score: float, max_age_seconds: int) -> dict[str, Any]:
    payload = {
        "state": state,
        "score": score,
        "max_age_seconds": max_age_seconds,
    }
    global _EYE_SIGNAL_WORKER_RUNNING, _EYE_SIGNAL_PENDING
    start_worker = False
    with _EYE_SIGNAL_LOCK:
        _EYE_SIGNAL_PENDING = {"state": state, "score": score, "max_age_seconds": max_age_seconds}
        if not _EYE_SIGNAL_WORKER_RUNNING:
            _EYE_SIGNAL_WORKER_RUNNING = True
            start_worker = True
    if start_worker:
        threading.Thread(target=_drain_eye_signal_queue, daemon=True).start()
    return payload


def _dispatch_eye_signal(payload: dict[str, Any]) -> None:
    state = str(payload.get("state", "looking_at_screen"))
    score = str(payload.get("score", 0.5))
    max_age = int(payload.get("max_age_seconds", 5))
    run_agent(
        [
            "signal",
            "eye_tracking",
            "--score",
            score,
            "--state",
            state,
            "--max-age-seconds",
            str(max_age),
            "--note",
            "derived-dev-monitor",
        ],
        timeout=5,
    )


def _drain_eye_signal_queue() -> None:
    global _EYE_SIGNAL_WORKER_RUNNING, _EYE_SIGNAL_LAST_DISPATCH, _EYE_SIGNAL_PENDING

    while True:
        payload: dict[str, Any] | None = None
        delay = 0.0
        with _EYE_SIGNAL_LOCK:
            now = time.monotonic()
            if _EYE_SIGNAL_PENDING is None:
                _EYE_SIGNAL_WORKER_RUNNING = False
                return

            wait = _EYE_SIGNAL_LAST_DISPATCH + EYE_SIGNAL_INTERVAL_SECONDS - now
            if wait > 0:
                delay = wait
            else:
                payload = _EYE_SIGNAL_PENDING
                _EYE_SIGNAL_PENDING = None
                _EYE_SIGNAL_LAST_DISPATCH = now

        if delay > 0:
            time.sleep(delay)
            continue

        if payload is not None:
            _dispatch_eye_signal(payload)


def reject_raw_payload(payload: dict[str, Any]) -> str | None:
    text = json.dumps(payload, sort_keys=True)
    if len(text.encode("utf-8")) > MAX_BODY_BYTES:
        return "payload too large"
    if RAW_SENSOR_PATTERNS.search(text):
        return "raw sensor/biometric payload rejected; send derived state only"
    return None


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _update_eye_freshness(eye: dict[str, Any]) -> None:
    observed = eye.get("observed_at")
    try:
        max_age = int(eye.get("max_age_seconds", 5))
    except (TypeError, ValueError):
        max_age = 5

    fresh = False
    if observed:
        try:
            dt = datetime.fromisoformat(str(observed).replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            dt = None
        if dt is not None:
            fresh = (datetime.now(UTC) - dt).total_seconds() <= max_age

    eye["fresh"] = fresh


def dev_state() -> dict[str, Any]:
    state = read_json_file(DEV_STATE_PATH)
    eye = state.get("eye")
    if isinstance(eye, dict):
        _update_eye_freshness(eye)
    correction = load_drift_correction()
    if correction is not None:
        state["drift_correction"] = correction
    return state


def store_eye_payload(payload: dict[str, Any]) -> dict[str, Any]:
    eye = build_eye_record(payload)
    state_payload = read_json_file(DEV_STATE_PATH)
    state_payload["eye"] = eye
    state_payload["updated_at"] = now_iso()
    write_json_file(DEV_STATE_PATH, state_payload)
    signal_state = eye.get("state") or "looking_at_screen"
    signal = queue_eye_signal(str(signal_state), float(eye.get("score", 0.5) or 0.5), int(eye.get("max_age_seconds", 5) or 5))
    return {"eye": eye, "signal": signal}


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
            elif path == "/dev/state":
                self.send_json(200, {"ok": True, **dev_state()})
            elif path == "/dev/eye":
                if parse_qs(parsed.query):
                    self.send_json(405, {"ok": False, "error": "use POST /dev/eye to update eye state"})
                else:
                    self.send_json(200, {"ok": True, **dev_state()})
            elif path == "/status":
                result = redacted_agent(["status", "--json"], timeout=4)
                self.send_json(200 if result.get("ok") else 502, result)
            elif path == "/signals":
                result = run_agent(["signals"], timeout=4)
                self.send_json(200 if result.get("ok") else 502, result)
            elif path == "/actions":
                result = run_agent(["actions"], timeout=4)
                self.send_json(200 if result.get("ok") else 502, result)
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
                score = bounded_float(payload["score"], 0.5, 0.0, 1.0, "score")
                weight = bounded_float(payload.get("weight"), 1.0, 0.0, 5.0, "weight")
                max_age = bounded_int(payload.get("max_age_seconds"), 30, 1, 3600, "max_age_seconds")
                command = [
                    "signal",
                    str(payload["name"]),
                    "--score",
                    str(score),
                    "--state",
                    str(payload.get("state", "derived")),
                    "--weight",
                    str(weight),
                    "--max-age-seconds",
                    str(max_age),
                ]
                if payload.get("eta_minutes") is not None:
                    eta = bounded_int(payload.get("eta_minutes"), 0, 0, 1440, "eta_minutes")
                    command.extend(["--eta-minutes", str(eta)])
                if payload.get("note"):
                    command.extend(["--note", str(payload["note"])])
                result = run_agent(command, timeout=4)
                self.send_json(200 if result.get("ok") else 502, result)
            elif path == "/dev/eye":
                self.send_json(200, {"ok": True, **store_eye_payload(payload)})
            elif path == "/correction/event":
                self.send_json(200, {"ok": True, "event": store_correction_event(payload)})
            elif path == "/action":
                max_age = bounded_int(payload.get("max_age_seconds"), 120, 1, 3600, "max_age_seconds")
                command = [
                    "action",
                    str(payload["direction"]),
                    str(payload["kind"]),
                    "--max-age-seconds",
                    str(max_age),
                ]
                if payload.get("score") is not None:
                    score = bounded_float(payload.get("score"), 0.5, 0.0, 1.0, "score")
                    command.extend(["--score", str(score)])
                if payload.get("weight") is not None:
                    weight = bounded_float(payload.get("weight"), 1.0, 0.0, 5.0, "weight")
                    command.extend(["--weight", str(weight)])
                if payload.get("state"):
                    command.extend(["--state", str(payload["state"])])
                if payload.get("eta_minutes") is not None:
                    eta = bounded_int(payload.get("eta_minutes"), 0, 0, 1440, "eta_minutes")
                    command.extend(["--eta-minutes", str(eta)])
                if payload.get("note"):
                    command.extend(["--note", str(payload["note"])])
                result = run_agent(command, timeout=4)
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
