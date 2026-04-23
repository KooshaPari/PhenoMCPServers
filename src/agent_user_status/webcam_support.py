"""Webcam and face-landmarker support for the derived gaze tracker."""

from __future__ import annotations

import math
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Screen:
    width: int
    height: int


@dataclass
class GazeSample:
    features: list[float]
    confidence: float


class TrackerError(RuntimeError):
    pass


STATE_DIR = Path(os.environ.get("AGENT_IMESSAGE_STATE_DIR", "~/.local/share/agent-imessage/state")).expanduser()
FACE_LANDMARKER_MODEL_URL = os.environ.get(
    "AGENT_USER_STATUS_FACE_LANDMARKER_MODEL_URL",
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
)
FACE_LANDMARKER_MODEL_PATH = Path(
    os.environ.get("AGENT_USER_STATUS_FACE_LANDMARKER_MODEL", str(STATE_DIR / "face_landmarker.task"))
).expanduser()

LEFT_EYE_OUTER = 33
LEFT_EYE_INNER = 133
RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 263
NOSE_TIP = 1
LEFT_IRIS = (468, 469, 470, 471, 472)
RIGHT_IRIS = (473, 474, 475, 476, 477)


def import_cv2() -> Any:
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError as exc:
        raise TrackerError("opencv-python is required. Install with: python3.11 -m pip install opencv-python") from exc
    return cv2


def import_numpy() -> Any:
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ImportError as exc:
        raise TrackerError("numpy is required. Install with: python3.11 -m pip install numpy") from exc
    return np


def import_mediapipe() -> Any:
    try:
        import mediapipe as mp  # type: ignore[import-not-found]
    except ImportError as exc:
        raise TrackerError("mediapipe is required. Install with: python3.11 -m pip install mediapipe") from exc
    return mp


def screen_size() -> Screen:
    try:
        from AppKit import NSScreen  # type: ignore[import-not-found]

        frame = NSScreen.mainScreen().frame()
        return Screen(width=int(frame.size.width), height=int(frame.size.height))
    except Exception:
        return Screen(
            width=int(os.environ.get("AGENT_USER_STATUS_SCREEN_WIDTH", "1440")),
            height=int(os.environ.get("AGENT_USER_STATUS_SCREEN_HEIGHT", "900")),
        )


def open_camera(camera: int, width: int, height: int) -> Any:
    cv2 = import_cv2()
    backend = cv2.CAP_AVFOUNDATION if hasattr(cv2, "CAP_AVFOUNDATION") else cv2.CAP_ANY
    for candidate in dict.fromkeys(value for value in (camera, 0, 1, 2, 3) if value >= 0):
        cap = cv2.VideoCapture(candidate, backend)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(candidate)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            return cap
        cap.release()
    raise TrackerError(
        "camera did not open. Grant Camera permission to the exact Python binary used by the "
        f"LaunchAgent ({sys.executable}), then retry."
    )


def ensure_face_landmarker_model() -> Path:
    if FACE_LANDMARKER_MODEL_PATH.exists() and FACE_LANDMARKER_MODEL_PATH.stat().st_size > 0:
        return FACE_LANDMARKER_MODEL_PATH
    FACE_LANDMARKER_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = FACE_LANDMARKER_MODEL_PATH.with_suffix(".task.tmp")
    try:
        urllib.request.urlretrieve(FACE_LANDMARKER_MODEL_URL, tmp_path)
        tmp_path.replace(FACE_LANDMARKER_MODEL_PATH)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise TrackerError(f"could not download Face Landmarker model: {exc}") from exc
    return FACE_LANDMARKER_MODEL_PATH


class FaceTracker:
    def __init__(self) -> None:
        self.mp = import_mediapipe()
        model_path = ensure_face_landmarker_model()
        BaseOptions = self.mp.tasks.BaseOptions
        FaceLandmarker = self.mp.tasks.vision.FaceLandmarker
        FaceLandmarkerOptions = self.mp.tasks.vision.FaceLandmarkerOptions
        VisionRunningMode = self.mp.tasks.vision.RunningMode
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=VisionRunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.55,
            min_face_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        self.landmarker = FaceLandmarker.create_from_options(options)
        self.last_timestamp_ms = 0

    def close(self) -> None:
        self.landmarker.close()

    def detect(self, rgb_frame: Any) -> Any:
        timestamp_ms = int(time.monotonic() * 1000)
        if timestamp_ms <= self.last_timestamp_ms:
            timestamp_ms = self.last_timestamp_ms + 1
        self.last_timestamp_ms = timestamp_ms
        mp_image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb_frame)
        return self.landmarker.detect_for_video(mp_image, timestamp_ms)


def create_face_mesh() -> FaceTracker:
    mp = import_mediapipe()
    if not hasattr(mp, "tasks"):
        raise TrackerError("installed mediapipe package does not expose the Tasks API")
    return FaceTracker()


def point(landmarks: list[Any], index: int) -> tuple[float, float]:
    lm = landmarks[index]
    return (float(lm.x), float(lm.y))


def mean_point(landmarks: list[Any], indices: tuple[int, ...]) -> tuple[float, float]:
    xs = [float(landmarks[index].x) for index in indices]
    ys = [float(landmarks[index].y) for index in indices]
    return (sum(xs) / len(xs), sum(ys) / len(ys))


def relative_iris(
    iris: tuple[float, float],
    outer: tuple[float, float],
    inner: tuple[float, float],
) -> tuple[float, float]:
    dx = inner[0] - outer[0]
    dy = inner[1] - outer[1]
    width = math.hypot(dx, dy)
    if width < 1e-6:
        return (0.5, 0.0)
    ux = dx / width
    uy = dy / width
    vx = -uy
    vy = ux
    px = iris[0] - outer[0]
    py = iris[1] - outer[1]
    return ((px * ux + py * uy) / width, (px * vx + py * vy) / width)


def frame_sample(face_mesh: FaceTracker, frame: Any) -> GazeSample | None:
    cv2 = import_cv2()
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = face_mesh.detect(rgb)
    if not result.face_landmarks:
        return None
    landmarks = result.face_landmarks[0]
    if len(landmarks) < 478:
        return None

    left_outer = point(landmarks, LEFT_EYE_OUTER)
    left_inner = point(landmarks, LEFT_EYE_INNER)
    right_inner = point(landmarks, RIGHT_EYE_INNER)
    right_outer = point(landmarks, RIGHT_EYE_OUTER)
    left_iris = mean_point(landmarks, LEFT_IRIS)
    right_iris = mean_point(landmarks, RIGHT_IRIS)
    nose = point(landmarks, NOSE_TIP)
    left_rel = relative_iris(left_iris, left_outer, left_inner)
    right_rel = relative_iris(right_iris, right_outer, right_inner)
    face_width = math.hypot(right_outer[0] - left_outer[0], right_outer[1] - left_outer[1])
    eye_asymmetry = left_rel[0] - right_rel[0]

    features = [
        left_rel[0],
        left_rel[1],
        right_rel[0],
        right_rel[1],
        nose[0],
        nose[1],
        face_width,
        eye_asymmetry,
    ]
    confidence = max(0.0, min(1.0, (face_width - 0.08) / 0.18))
    return GazeSample(features=features, confidence=confidence)
