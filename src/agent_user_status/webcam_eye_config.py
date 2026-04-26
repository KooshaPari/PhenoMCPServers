"""Configuration helpers for the opt-in webcam gaze tracker."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from agent_user_status.webcam_support import FaceTrackerThresholds, TrackerError, import_numpy

STATE_DIR = Path(os.environ.get("AGENT_IMESSAGE_STATE_DIR", "~/.local/share/agent-imessage/state")).expanduser()
CALIBRATION_PATH = Path(
    os.environ.get("AGENT_USER_STATUS_EYE_CALIBRATION", str(STATE_DIR / "eye_calibration.json"))
).expanduser()
STATUSD_URL = os.environ.get("AGENT_USER_STATUSD_URL", "http://127.0.0.1:8765")


def default_camera() -> int:
    try:
        return int(os.environ.get("AGENT_USER_STATUS_EYE_CAMERA", "0"))
    except ValueError:
        return 0


def load_calibration(path: Path = CALIBRATION_PATH) -> dict[str, Any]:
    if not path.exists():
        raise TrackerError(f"calibration missing: run `agent-user-status-webcam-eye-tracker calibrate` first ({path})")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("kind") != "mediapipe_iris_regression":
        raise TrackerError(f"unsupported calibration kind in {path}")
    return payload


def summarize_errors(errors: list[float]) -> dict[str, float]:
    if not errors:
        return {"mean_error_px": 0.0, "p95_error_px": 0.0, "max_error_px": 0.0}
    np = import_numpy()
    ordered = np.asarray(errors, dtype=float)
    return {
        "mean_error_px": float(ordered.mean()),
        "p95_error_px": float(np.percentile(ordered, 95)),
        "max_error_px": float(ordered.max()),
    }


def tracker_thresholds(args: argparse.Namespace) -> FaceTrackerThresholds:
    return FaceTrackerThresholds(
        detection=float(args.min_face_detection_confidence),
        presence=float(args.min_face_presence_confidence),
        tracking=float(args.min_tracking_confidence),
    )
