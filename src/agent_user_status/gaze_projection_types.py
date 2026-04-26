"""Shared projection data types and geometry helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ScreenLike(Protocol):
    @property
    def width(self) -> int: ...

    @property
    def height(self) -> int: ...


@dataclass(frozen=True)
class ProjectionDecision:
    publish_point: tuple[float, float]
    smooth_point: tuple[float, float] | None
    anchor_point: tuple[float, float] | None
    mode: str
    hold_active: bool
    hold_reason: str
    hold_hint: str
    should_reset: bool
    projection_error_px: float
    projection_offscreen_px: float
    hold_threshold_px: float
    release_threshold_px: float
    recovery_score: float
    stable_frames: int
    hold_budget_frames: int
    targeting_reliable: bool


class StableSampleGate:
    def __init__(self, min_confidence: float = 0.35, min_frames: int = 2) -> None:
        self.min_confidence = min_confidence
        self.min_frames = max(1, min_frames)
        self.frames = 0
        self.last_confidence: float | None = None
        self.max_confidence_delta = 0.16

    def update(self, confidence: float) -> bool:
        if confidence >= self.min_confidence:
            if (
                self.last_confidence is not None
                and self.frames > 0
                and abs(confidence - self.last_confidence) > self.max_confidence_delta
            ):
                self.frames = 0
            else:
                self.frames += 1
            self.last_confidence = confidence
        else:
            self.frames = 0
            self.last_confidence = confidence
        return self.ready()

    def ready(self) -> bool:
        return self.frames >= self.min_frames

    def reset(self) -> None:
        self.frames = 0
        self.last_confidence = None


def clamp_point(point: tuple[float, float], screen: ScreenLike) -> tuple[float, float]:
    return (
        max(0.0, min(float(screen.width - 1), point[0])),
        max(0.0, min(float(screen.height - 1), point[1])),
    )


def in_bounds(point: tuple[float, float], screen: ScreenLike) -> bool:
    return 0.0 <= point[0] <= float(screen.width - 1) and 0.0 <= point[1] <= float(screen.height - 1)


def screen_center(screen: ScreenLike) -> tuple[float, float]:
    return (float(screen.width - 1) / 2.0, float(screen.height - 1) / 2.0)
