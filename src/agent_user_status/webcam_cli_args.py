"""Shared CLI argument groups for the opt-in webcam eye tracker."""

from __future__ import annotations

import argparse

from agent_user_status.webcam_eye_config import default_camera


def add_camera_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--camera", type=int, default=default_camera())
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)


def add_tracker_threshold_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--min-face-detection-confidence", type=float, default=0.2)
    parser.add_argument("--min-face-presence-confidence", type=float, default=0.2)
    parser.add_argument("--min-tracking-confidence", type=float, default=0.2)


def add_acquisition_args(parser: argparse.ArgumentParser) -> None:
    add_camera_args(parser)
    add_tracker_threshold_args(parser)
