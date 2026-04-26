from __future__ import annotations

from dataclasses import dataclass

import pytest

from agent_user_status.gaze_calibration import projection_thresholds
from agent_user_status.gaze_projection import ProjectionHoldGate, StableSampleGate


@dataclass(frozen=True)
class Screen:
    width: int
    height: int


@pytest.mark.requirement("FR-age-001")
def test_projection_hold_keeps_last_trusted_point_when_raw_prediction_goes_offscreen() -> None:
    screen = Screen(width=1440, height=900)
    gate = ProjectionHoldGate(
        hold_threshold_px=120.0,
        release_threshold_px=68.0,
        calibration_quality_score=0.9,
        enter_frames=1,
        release_frames=2,
    )

    tracking = gate.update((620.0, 410.0), screen, confidence=0.91, stability_score=0.88)
    assert tracking.mode == "tracking"
    assert tracking.anchor_point == (620.0, 410.0)
    assert tracking.targeting_reliable is True

    hold = gate.update((1750.0, 1180.0), screen, confidence=0.9, stability_score=0.86)
    assert hold.mode == "projection_hold"
    assert hold.hold_reason == "offscreen_jump"
    assert hold.anchor_point == (620.0, 410.0)
    assert hold.publish_point == (620.0, 410.0)
    assert hold.smooth_point is None
    assert hold.targeting_reliable is False
    assert hold.projection_offscreen_px > 0


@pytest.mark.requirement("FR-age-001")
def test_projection_hold_releases_only_after_projection_returns_in_bounds() -> None:
    screen = Screen(width=1440, height=900)
    gate = ProjectionHoldGate(
        hold_threshold_px=120.0,
        release_threshold_px=68.0,
        calibration_quality_score=0.9,
        enter_frames=1,
        release_frames=2,
    )

    gate.update((640.0, 360.0), screen, confidence=0.93, stability_score=0.9)
    gate.update((1760.0, 1220.0), screen, confidence=0.89, stability_score=0.84)

    still_held = gate.update((1750.0, 1200.0), screen, confidence=0.94, stability_score=0.9)
    assert still_held.mode == "projection_hold"
    assert still_held.hold_reason == "offscreen_jump"
    assert still_held.targeting_reliable is False

    recovering = gate.update((646.0, 366.0), screen, confidence=0.95, stability_score=0.92)
    assert recovering.mode == "projection_hold"
    assert recovering.hold_reason == "recovering"
    assert recovering.recovery_score > 0.0
    assert recovering.targeting_reliable is False

    released = gate.update((648.0, 364.0), screen, confidence=0.95, stability_score=0.92)
    assert released.mode == "projection_hold_recovering"
    assert released.hold_reason == "recovered"
    assert released.should_reset is True
    assert released.targeting_reliable is True


@pytest.mark.requirement("FR-age-001")
def test_poor_calibration_stays_in_degraded_hold_until_recovery() -> None:
    screen = Screen(width=1440, height=900)
    gate = ProjectionHoldGate(
        hold_threshold_px=120.0,
        release_threshold_px=68.0,
        calibration_quality_score=0.12,
        calibration_recommended_action="recalibrate",
        enter_frames=1,
        release_frames=3,
    )

    gate.update((640.0, 360.0), screen, confidence=0.93, stability_score=0.9)
    gate.update((1760.0, 1220.0), screen, confidence=0.89, stability_score=0.84)

    degraded = gate.update((1754.0, 1212.0), screen, confidence=0.9, stability_score=0.86)
    assert degraded.mode == "projection_hold_degraded"
    assert degraded.hold_active is True
    assert degraded.should_reset is False
    assert degraded.hold_reason == "poor_calibration_fit"
    assert degraded.hold_budget_frames == 2
    assert "recalibrate" in degraded.hold_hint
    assert "degraded hold remains active" in degraded.hold_hint
    assert degraded.targeting_reliable is False


@pytest.mark.requirement("FR-age-001")
def test_projection_thresholds_shrink_when_calibration_quality_is_poor() -> None:
    screen = Screen(width=1440, height=900)
    poor = projection_thresholds(
        {
            "mean_error_px": 24.0,
            "p95_error_px": 58.0,
            "calibration_quality_score": 0.18,
        },
        screen,
    )
    strong = projection_thresholds(
        {
            "mean_error_px": 24.0,
            "p95_error_px": 58.0,
            "calibration_quality_score": 0.91,
        },
        screen,
    )

    assert poor[0] < strong[0]
    assert poor[1] <= strong[1]


@pytest.mark.requirement("FR-age-001")
def test_stable_sample_gate_resets_on_confidence_jitter_before_it_is_ready() -> None:
    gate = StableSampleGate(min_confidence=0.35, min_frames=3)

    assert gate.update(0.36) is False
    assert gate.update(0.37) is False
    assert gate.frames == 2
    assert gate.update(0.56) is False
    assert gate.frames == 0
    assert gate.update(0.57) is False
    assert gate.update(0.58) is False
    assert gate.update(0.59) is True
