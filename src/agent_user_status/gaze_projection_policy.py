"""Projection-hold policy helpers."""

from __future__ import annotations

from agent_user_status.gaze_projection_types import ScreenLike, clamp_point, in_bounds, screen_center


def quality_label(calibration_quality_score: float) -> str:
    if calibration_quality_score <= 0.35:
        return "poor"
    if calibration_quality_score <= 0.55:
        return "fragile"
    if calibration_quality_score <= 0.78:
        return "usable"
    return "excellent"


def hold_budget_frames(calibration_quality_score: float) -> int:
    if calibration_quality_score <= 0.35:
        return 2
    if calibration_quality_score <= 0.55:
        return 3
    return 0


def effective_release_frames(calibration_quality_score: float, release_frames: int) -> int:
    if calibration_quality_score <= 0.35:
        return max(release_frames, 4)
    if calibration_quality_score <= 0.55:
        return max(release_frames, 3)
    return release_frames


def anchor_point(
    last_trusted_point: tuple[float, float] | None,
    fallback_point: tuple[float, float] | None,
    screen: ScreenLike,
) -> tuple[float, float]:
    if last_trusted_point is not None:
        return clamp_point(last_trusted_point, screen)
    if fallback_point is not None and in_bounds(fallback_point, screen):
        return clamp_point(fallback_point, screen)
    return screen_center(screen)


def hold_reason(
    raw_point: tuple[float, float],
    screen: ScreenLike,
    error_px: float,
    confidence: float,
    stability_score: float,
    recovery_signal: bool,
    calibration_quality_score: float,
    min_confidence: float,
    hold_threshold_px: float,
) -> str:
    if recovery_signal:
        return "recovering"
    if calibration_quality_score <= 0.35:
        return "poor_calibration_fit"
    if not in_bounds(raw_point, screen):
        return "offscreen_jump"
    if confidence < min_confidence:
        return "low_confidence"
    if stability_score < 0.32:
        return "unstable_projection"
    if error_px >= hold_threshold_px:
        return "projection_outlier"
    return "projection_pending"


def recovery_score(
    error_px: float,
    confidence: float,
    stability_score: float,
    release_threshold_px: float,
    hold_threshold_px: float,
    min_confidence: float,
    calibration_quality_score: float,
) -> float:
    if release_threshold_px >= hold_threshold_px:
        proximity = 1.0 if error_px <= release_threshold_px else 0.0
    else:
        proximity = 1.0 - min(
            1.0,
            max(0.0, (error_px - release_threshold_px) / (hold_threshold_px - release_threshold_px)),
        )
    quality = max(
        0.0,
        min(
            1.0,
            0.45 * (confidence / max(min_confidence, 1e-6))
            + 0.35 * stability_score
            + 0.20 * calibration_quality_score,
        ),
    )
    return max(0.0, min(1.0, 0.65 * proximity + 0.35 * quality))


def hold_hint(
    reason: str,
    recovery_signal: bool,
    release_frames: int,
    budget_frames: int,
    release_threshold_px: float,
    hold_threshold_px: float,
    calibration_quality_score: float,
) -> str:
    if recovery_signal:
        return (
            f"projection is back inside screen bounds; release after one more stable frame "
            f"({release_threshold_px:.0f}px release / {hold_threshold_px:.0f}px hold)"
        )
    if reason == "poor_calibration_fit":
        return (
            f"poor calibration fit ({quality_label(calibration_quality_score)}); recalibrate soon; "
            f"degraded hold stays active until recovery is sustained for {release_frames} frames "
            f"({release_threshold_px:.0f}px release / {hold_threshold_px:.0f}px hold)"
        )
    if reason == "offscreen_jump":
        return (
            f"projection is offscreen; move gaze back inside the screen and keep it steady for {release_frames} frames "
            f"({release_threshold_px:.0f}px release / {hold_threshold_px:.0f}px hold)"
        )
    if reason == "low_confidence":
        return (
            f"camera confidence is too low; hold keeps the last trusted point and will release after "
            f"{release_frames} stable frames ({release_threshold_px:.0f}px release / {hold_threshold_px:.0f}px hold)"
        )
    if reason == "unstable_projection":
        return (
            f"projection is unstable; slow down head motion and keep gaze steady for {release_frames} frames "
            f"({release_threshold_px:.0f}px release / {hold_threshold_px:.0f}px hold)"
        )
    if reason == "projection_outlier":
        return f"projection jumped past the hold threshold ({hold_threshold_px:.0f}px); recalibrate if this repeats"
    if budget_frames > 0:
        return (
            f"hold budget is {budget_frames} frames before degraded release; recalibrate if the fit stays poor "
            f"({release_threshold_px:.0f}px release / {hold_threshold_px:.0f}px hold)"
        )
    return "freeze at the last trusted point until the projection returns in bounds"


def degraded_hold_hint(
    calibration_quality_score: float,
    release_frames: int,
    calibration_recommended_action: str,
) -> str:
    return (
        f"poor calibration fit ({quality_label(calibration_quality_score)}); degraded hold remains active until "
        f"recovery is sustained for {release_frames} frames; {calibration_recommended_action.replace('_', ' ')}"
    )
