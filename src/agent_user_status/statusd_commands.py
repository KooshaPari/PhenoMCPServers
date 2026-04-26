"""Command builders for statusd POST routes."""

from __future__ import annotations

from typing import Any

from agent_user_status.eye_state_payload import bounded_float, bounded_int


def append_common_signal_options(command: list[str], payload: dict[str, Any]) -> None:
    if payload.get("eta_minutes") is not None:
        eta = bounded_int(payload.get("eta_minutes"), 0, 0, 1440, "eta_minutes")
        command.extend(["--eta-minutes", str(eta)])
    if payload.get("note"):
        command.extend(["--note", str(payload["note"])])


def build_signal_command(payload: dict[str, Any]) -> list[str]:
    score = bounded_float(payload["score"], 0.5, 0.0, 1.0, "score")
    weight = bounded_float(payload.get("weight"), 1.0, 0.0, 5.0, "weight")
    max_age = bounded_int(payload.get("max_age_seconds"), 30, 1, 3600, "max_age_seconds")
    command = [
        "signal",
        str(payload["name"]),
        "--score",
        str(score),
        "--state",
        str(payload.get("state", "derived")),
        "--weight",
        str(weight),
        "--max-age-seconds",
        str(max_age),
    ]
    append_common_signal_options(command, payload)
    return command


def build_action_command(payload: dict[str, Any]) -> list[str]:
    max_age = bounded_int(payload.get("max_age_seconds"), 120, 1, 3600, "max_age_seconds")
    command = [
        "action",
        str(payload["direction"]),
        str(payload["kind"]),
        "--max-age-seconds",
        str(max_age),
    ]
    if payload.get("score") is not None:
        score = bounded_float(payload.get("score"), 0.5, 0.0, 1.0, "score")
        command.extend(["--score", str(score)])
    if payload.get("weight") is not None:
        weight = bounded_float(payload.get("weight"), 1.0, 0.0, 5.0, "weight")
        command.extend(["--weight", str(weight)])
    if payload.get("state"):
        command.extend(["--state", str(payload["state"])])
    append_common_signal_options(command, payload)
    return command
