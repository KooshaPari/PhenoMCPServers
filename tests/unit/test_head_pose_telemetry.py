from __future__ import annotations

from dataclasses import dataclass

from agent_user_status.eye_state_payload import build_eye_record
from agent_user_status.webcam_support import derived_head_telemetry


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float


def landmarks() -> list[Landmark]:
    points = [Landmark(0.5, 0.5) for _ in range(478)]
    points[1] = Landmark(0.51, 0.47)
    points[10] = Landmark(0.5, 0.24)
    points[33] = Landmark(0.38, 0.42)
    points[133] = Landmark(0.46, 0.42)
    points[152] = Landmark(0.5, 0.74)
    points[263] = Landmark(0.62, 0.43)
    points[362] = Landmark(0.54, 0.42)
    return points


def test_derived_head_telemetry_contains_only_abstract_values() -> None:
    telemetry = derived_head_telemetry(
        landmarks(),
        left_outer=(0.38, 0.42),
        right_outer=(0.62, 0.43),
        nose=(0.51, 0.47),
        face_width=0.24,
    )

    assert set(telemetry) == {
        "head_yaw_deg",
        "head_pitch_deg",
        "head_roll_deg",
        "head_span_width_norm",
        "head_span_height_norm",
        "framing_quality",
        "framing_state",
    }
    assert telemetry["framing_state"] == "usable"
    assert "landmark" not in str(telemetry).lower()


def test_eye_record_accepts_head_pose_without_raw_sensor_payload() -> None:
    record = build_eye_record(
        {
            "score": 0.7,
            "state": "looking_at_screen",
            "head_yaw_deg": 12.5,
            "head_pitch_deg": -4.25,
            "head_roll_deg": 2.0,
            "head_span_width_norm": 0.31,
            "head_span_height_norm": 0.5,
            "framing_quality": 0.86,
            "framing_state": "usable",
        }
    )

    assert record["head_yaw_deg"] == 12.5
    assert record["head_pitch_deg"] == -4.25
    assert record["framing_quality"] == 0.86
    assert record["framing_state"] == "usable"
