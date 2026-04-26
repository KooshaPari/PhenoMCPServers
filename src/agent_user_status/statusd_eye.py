"""Derived eye/dev-state helpers for the local status backend."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_user_status.eye_state_payload import build_eye_record, now_iso
from agent_user_status.gaze_drift_correction import load_drift_correction

EYE_SIGNAL_INTERVAL_SECONDS = float(os.environ.get("AGENT_USER_STATUSD_EYE_SIGNAL_INTERVAL_SECONDS", "1.0"))

_EYE_SIGNAL_LOCK = threading.Lock()
_EYE_SIGNAL_WORKER_RUNNING = False
_EYE_SIGNAL_PENDING: dict[str, Any] | None = None
_EYE_SIGNAL_LAST_DISPATCH = 0.0

RunAgent = Callable[[list[str], int], dict[str, Any]]


def queue_eye_signal(
    state: str,
    score: float,
    max_age_seconds: int,
    run_agent: RunAgent,
) -> dict[str, Any]:
    payload = {
        "state": state,
        "score": score,
        "max_age_seconds": max_age_seconds,
    }
    global _EYE_SIGNAL_WORKER_RUNNING, _EYE_SIGNAL_PENDING
    start_worker = False
    with _EYE_SIGNAL_LOCK:
        _EYE_SIGNAL_PENDING = payload
        if not _EYE_SIGNAL_WORKER_RUNNING:
            _EYE_SIGNAL_WORKER_RUNNING = True
            start_worker = True
    if start_worker:
        threading.Thread(target=_drain_eye_signal_queue, args=(run_agent,), daemon=True).start()
    return payload


def _dispatch_eye_signal(payload: dict[str, Any], run_agent: RunAgent) -> None:
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
        5,
    )


def _drain_eye_signal_queue(run_agent: RunAgent) -> None:
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
            _dispatch_eye_signal(payload, run_agent)


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def write_json_file(state_dir: Path, path: Path, payload: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
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


def dev_state(dev_state_path: Path) -> dict[str, Any]:
    state = read_json_file(dev_state_path)
    eye = state.get("eye")
    if isinstance(eye, dict):
        _update_eye_freshness(eye)
    correction = load_drift_correction()
    if correction is not None:
        state["drift_correction"] = correction
    return state


def store_eye_payload(
    payload: dict[str, Any],
    state_dir: Path,
    dev_state_path: Path,
    run_agent: RunAgent,
) -> dict[str, Any]:
    eye = build_eye_record(payload)
    state_payload = read_json_file(dev_state_path)
    state_payload["eye"] = eye
    state_payload["updated_at"] = now_iso()
    write_json_file(state_dir, dev_state_path, state_payload)
    signal_state = eye.get("state") or "looking_at_screen"
    signal = queue_eye_signal(
        str(signal_state),
        float(eye.get("score", 0.5) or 0.5),
        int(eye.get("max_age_seconds", 5) or 5),
        run_agent,
    )
    return {"eye": eye, "signal": signal}
