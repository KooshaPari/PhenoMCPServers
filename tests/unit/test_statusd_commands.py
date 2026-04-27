from __future__ import annotations

import pytest

from agent_user_status.statusd_commands import build_action_command, build_signal_command


@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_build_signal_command_includes_defaults_and_common_options() -> None:
    command = build_signal_command(
        {
            "name": "process_tracker",
            "score": "0.75",
            "eta_minutes": "12",
            "note": "focused editor",
        }
    )

    assert command == [
        "signal",
        "process_tracker",
        "--score",
        "0.75",
        "--state",
        "derived",
        "--weight",
        "1.0",
        "--max-age-seconds",
        "30",
        "--eta-minutes",
        "12",
        "--note",
        "focused editor",
    ]


@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_build_action_command_includes_optional_score_weight_state_and_common_options() -> None:
    command = build_action_command(
        {
            "direction": "input",
            "kind": "mouse_click",
            "max_age_seconds": "45",
            "score": "0.6",
            "weight": "2.5",
            "state": "active",
            "eta_minutes": 3,
            "note": "recent input",
        }
    )

    assert command == [
        "action",
        "input",
        "mouse_click",
        "--max-age-seconds",
        "45",
        "--score",
        "0.6",
        "--weight",
        "2.5",
        "--state",
        "active",
        "--eta-minutes",
        "3",
        "--note",
        "recent input",
    ]


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"name": "eye_tracking", "score": 1.1}, "score must be between 0.0 and 1.0"),
        ({"name": "eye_tracking", "score": 0.8, "weight": 5.1}, "weight must be between 0.0 and 5.0"),
        (
            {"name": "eye_tracking", "score": 0.8, "max_age_seconds": 0},
            "max_age_seconds must be between 1 and 3600",
        ),
        ({"name": "eye_tracking", "score": 0.8, "eta_minutes": 1441}, "eta_minutes must be between 0 and 1440"),
    ],
)
@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_build_signal_command_rejects_out_of_range_values(payload: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_signal_command(payload)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"direction": "input", "kind": "key_press", "score": -0.1}, "score must be between 0.0 and 1.0"),
        ({"direction": "input", "kind": "key_press", "weight": -0.1}, "weight must be between 0.0 and 5.0"),
        (
            {"direction": "input", "kind": "key_press", "max_age_seconds": 3601},
            "max_age_seconds must be between 1 and 3600",
        ),
        (
            {"direction": "input", "kind": "key_press", "eta_minutes": -1},
            "eta_minutes must be between 0 and 1440",
        ),
    ],
)
@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_build_action_command_rejects_out_of_range_values(payload: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_action_command(payload)


@pytest.mark.parametrize(
    ("builder", "payload", "missing_key"),
    [
        (build_signal_command, {"score": 0.8}, "name"),
        (build_signal_command, {"name": "eye_tracking"}, "score"),
        (build_action_command, {"kind": "key_press"}, "direction"),
        (build_action_command, {"direction": "input"}, "kind"),
    ],
)
@pytest.mark.requirement("FR-AGENT_USER_STATUS-004")
def test_command_builders_require_route_keys(builder, payload: dict[str, object], missing_key: str) -> None:
    with pytest.raises(KeyError, match=missing_key):
        builder(payload)
