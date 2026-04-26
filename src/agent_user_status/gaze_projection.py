"""Projection-hold recovery helpers."""

from __future__ import annotations

from agent_user_status.eye_smoothing import projection_error
from agent_user_status.gaze_projection_policy import (
    anchor_point,
    degraded_hold_hint,
    hold_hint,
    hold_reason,
    recovery_score,
)
from agent_user_status.gaze_projection_policy import (
    effective_release_frames as policy_effective_release_frames,
)
from agent_user_status.gaze_projection_policy import (
    hold_budget_frames as policy_hold_budget_frames,
)
from agent_user_status.gaze_projection_types import (
    ProjectionDecision,
    ScreenLike,
    StableSampleGate,
    clamp_point,
    in_bounds,
    screen_center,
)

__all__ = [
    "ProjectionDecision",
    "ProjectionHoldGate",
    "ScreenLike",
    "StableSampleGate",
    "clamp_point",
    "in_bounds",
    "screen_center",
]


class ProjectionHoldGate:
    def __init__(
        self,
        hold_threshold_px: float,
        release_threshold_px: float,
        calibration_quality_score: float = 0.0,
        calibration_recommended_action: str = "monitor",
        min_confidence: float = 0.36,
        enter_frames: int = 2,
        release_frames: int = 3,
    ) -> None:
        self.hold_threshold_px = hold_threshold_px
        self.release_threshold_px = release_threshold_px
        self.calibration_quality_score = max(0.0, min(1.0, calibration_quality_score))
        self.calibration_recommended_action = calibration_recommended_action
        self.min_confidence = min_confidence
        self.enter_frames = max(1, enter_frames)
        self.release_frames = max(1, release_frames)
        self.hold_frames = 0
        self.recovery_frames = 0
        self.hold_active = False
        self.last_trusted_point: tuple[float, float] | None = None
        self.last_error_px = 0.0

    def _anchor_point(
        self,
        fallback_point: tuple[float, float] | None,
        screen: ScreenLike,
    ) -> tuple[float, float]:
        return anchor_point(self.last_trusted_point, fallback_point, screen)

    def _hold_reason(
        self,
        raw_point: tuple[float, float],
        screen: ScreenLike,
        error_px: float,
        confidence: float,
        stability_score: float,
        recovery_signal: bool,
    ) -> str:
        return hold_reason(
            raw_point,
            screen,
            error_px,
            confidence,
            stability_score,
            recovery_signal,
            self.calibration_quality_score,
            self.min_confidence,
            self.hold_threshold_px,
        )

    def _recovery_score(self, error_px: float, confidence: float, stability_score: float) -> float:
        return recovery_score(
            error_px,
            confidence,
            stability_score,
            self.release_threshold_px,
            self.hold_threshold_px,
            self.min_confidence,
            self.calibration_quality_score,
        )

    def _hold_hint(
        self,
        reason: str,
        recovery_signal: bool,
        effective_release_frames: int,
        budget_frames: int,
    ) -> str:
        return hold_hint(
            reason,
            recovery_signal,
            effective_release_frames,
            budget_frames,
            self.release_threshold_px,
            self.hold_threshold_px,
            self.calibration_quality_score,
        )

    def update(
        self,
        raw_point: tuple[float, float],
        screen: ScreenLike,
        confidence: float,
        stability_score: float,
        fallback_point: tuple[float, float] | None = None,
    ) -> ProjectionDecision:
        error_px = projection_error(raw_point, screen)
        raw_in_bounds = in_bounds(raw_point, screen)
        improving = error_px <= self.last_error_px * 0.86 if self.last_error_px > 0 else False
        effective_release_frames = policy_effective_release_frames(self.calibration_quality_score, self.release_frames)
        hold_budget_frames = policy_hold_budget_frames(self.calibration_quality_score)
        recovery_signal = raw_in_bounds and (
            error_px <= self.release_threshold_px
            or (improving and error_px <= self.hold_threshold_px * 1.15)
            or (
                confidence >= self.min_confidence + 0.06
                and stability_score >= 0.33
                and error_px <= self.hold_threshold_px
            )
        )
        self.last_error_px = error_px
        anchor_point = self._anchor_point(fallback_point, screen)
        hold_reason = self._hold_reason(raw_point, screen, error_px, confidence, stability_score, recovery_signal)

        if self.hold_active:
            self.hold_frames += 1
            if recovery_signal:
                self.recovery_frames += 1
            else:
                self.recovery_frames = 0
            if self.recovery_frames >= effective_release_frames:
                self.hold_active = False
                self.hold_frames = 0
                self.recovery_frames = 0
                self.last_trusted_point = raw_point if raw_in_bounds else anchor_point
                return ProjectionDecision(
                    publish_point=raw_point,
                    smooth_point=raw_point,
                    anchor_point=anchor_point,
                    mode="projection_hold_recovering",
                    hold_active=False,
                    hold_reason="recovered",
                    hold_hint="resume tracking; projection is back inside screen bounds",
                    should_reset=True,
                    projection_error_px=round(error_px, 2),
                    projection_offscreen_px=round(error_px if not raw_in_bounds else 0.0, 2),
                    hold_threshold_px=round(self.hold_threshold_px, 2),
                    release_threshold_px=round(self.release_threshold_px, 2),
                    recovery_score=round(self._recovery_score(error_px, confidence, stability_score), 4),
                    stable_frames=self.recovery_frames,
                    hold_budget_frames=hold_budget_frames,
                    targeting_reliable=confidence >= self.min_confidence and stability_score >= 0.38 and raw_in_bounds,
                )
            if hold_budget_frames > 0 and self.hold_frames >= hold_budget_frames:
                self.hold_frames = hold_budget_frames
                return ProjectionDecision(
                    publish_point=anchor_point,
                    smooth_point=None,
                    anchor_point=anchor_point,
                    mode="projection_hold_degraded",
                    hold_active=True,
                    hold_reason=hold_reason,
                    hold_hint=degraded_hold_hint(
                        self.calibration_quality_score,
                        effective_release_frames,
                        self.calibration_recommended_action,
                    ),
                    should_reset=False,
                    projection_error_px=round(error_px, 2),
                    projection_offscreen_px=round(error_px if not raw_in_bounds else 0.0, 2),
                    hold_threshold_px=round(self.hold_threshold_px, 2),
                    release_threshold_px=round(self.release_threshold_px, 2),
                    recovery_score=round(self._recovery_score(error_px, confidence, stability_score), 4),
                    stable_frames=self.hold_frames,
                    hold_budget_frames=hold_budget_frames,
                    targeting_reliable=False,
                )

            anchor = anchor_point
            return ProjectionDecision(
                publish_point=anchor,
                smooth_point=None,
                anchor_point=anchor,
                mode="projection_hold",
                hold_active=True,
                hold_reason=hold_reason,
                hold_hint=self._hold_hint(hold_reason, recovery_signal, effective_release_frames, hold_budget_frames),
                should_reset=False,
                projection_error_px=round(error_px, 2),
                projection_offscreen_px=round(error_px if not raw_in_bounds else 0.0, 2),
                hold_threshold_px=round(self.hold_threshold_px, 2),
                release_threshold_px=round(self.release_threshold_px, 2),
                recovery_score=round(
                    max(
                        self.recovery_frames / effective_release_frames,
                        self._recovery_score(error_px, confidence, stability_score),
                    ),
                    4,
                ),
                stable_frames=self.recovery_frames,
                hold_budget_frames=hold_budget_frames,
                targeting_reliable=False,
            )

        if error_px <= self.hold_threshold_px and confidence >= self.min_confidence and stability_score >= 0.28:
            self.hold_frames = 0
            self.last_trusted_point = raw_point
            return ProjectionDecision(
                publish_point=raw_point,
                smooth_point=raw_point,
                anchor_point=raw_point,
                mode="tracking",
                hold_active=False,
                hold_reason="tracking",
                hold_hint="tracking is stable",
                should_reset=False,
                projection_error_px=round(error_px, 2),
                projection_offscreen_px=0.0,
                hold_threshold_px=round(self.hold_threshold_px, 2),
                release_threshold_px=round(self.release_threshold_px, 2),
                recovery_score=0.0,
                stable_frames=0,
                hold_budget_frames=hold_budget_frames,
                targeting_reliable=True,
            )

        self.hold_frames += 1
        self.recovery_frames = 0
        if raw_in_bounds:
            self.last_trusted_point = raw_point
        if self.hold_frames < self.enter_frames:
            clamped = anchor_point if not raw_in_bounds else clamp_point(raw_point, screen)
            return ProjectionDecision(
                publish_point=clamped,
                smooth_point=clamped,
                anchor_point=anchor_point,
                mode="projection_pending",
                hold_active=False,
                hold_reason=hold_reason,
                hold_hint="await one more stable frame before freezing the point",
                should_reset=False,
                projection_error_px=round(error_px, 2),
                projection_offscreen_px=round(error_px if not raw_in_bounds else 0.0, 2),
                hold_threshold_px=round(self.hold_threshold_px, 2),
                release_threshold_px=round(self.release_threshold_px, 2),
                recovery_score=round(self._recovery_score(error_px, confidence, stability_score), 4),
                stable_frames=self.hold_frames,
                hold_budget_frames=hold_budget_frames,
                targeting_reliable=raw_in_bounds and confidence >= self.min_confidence and stability_score >= 0.28,
            )

        self.hold_active = True
        anchor = anchor_point
        return ProjectionDecision(
            publish_point=anchor,
            smooth_point=None,
            anchor_point=anchor,
            mode="projection_hold",
            hold_active=True,
            hold_reason=hold_reason,
            hold_hint="freeze at the last trusted point until the projection returns in bounds",
            should_reset=False,
            projection_error_px=round(error_px, 2),
            projection_offscreen_px=round(error_px if not raw_in_bounds else 0.0, 2),
            hold_threshold_px=round(self.hold_threshold_px, 2),
            release_threshold_px=round(self.release_threshold_px, 2),
            recovery_score=round(self._recovery_score(error_px, confidence, stability_score), 4),
            stable_frames=self.hold_frames,
            hold_budget_frames=hold_budget_frames,
            targeting_reliable=False,
        )
