"""Shared bootstrap constants and path helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BootstrapPaths:
    root: Path
    src: Path
    launchd_src: Path
    bin_dir: Path
    share_dir: Path
    launchd_dir: Path
    state_dir: Path
    eye_venv: Path

SUPPORT_MODULES = [
    "bootstrap.py",
    "bootstrap_support.py",
    "agent_imessage_action_learning.py",
    "agent_imessage_comm_commands.py",
    "agent_imessage_core.py",
    "agent_imessage_elicitation.py",
    "agent_imessage_envelope.py",
    "agent_imessage_learning.py",
    "agent_imessage_mcp_comm.py",
    "agent_imessage_mcp_install.py",
    "agent_imessage_mcp_presence.py",
    "agent_imessage_mcp_sessions.py",
    "agent_imessage_outbox.py",
    "agent_imessage_presence_commands.py",
    "agent_imessage_session_commands.py",
    "agent_imessage_signals.py",
    "agent_imessage_state_commands.py",
    "agent_imessage_status.py",
    "agent_imessage_commands.py",
    "bootstrap_native.py",
    "correction.py",
    "session_privacy.py",
    "session_registry.py",
    "session_scan.py",
    "gaze_context.py",
    "gaze_drift_correction.py",
    "gaze_evaluation.py",
    "gaze_calibration.py",
    "gaze_projection.py",
    "gaze_projection_policy.py",
    "gaze_projection_types.py",
    "eye_state_payload.py",
    "webcam_eye_config.py",
    "webcam_probe.py",
    "webcam_runtime.py",
    "webcam_support.py",
    "eye_publish.py",
    "eye_smoothing.py",
    "monitor_html.py",
    "state_retention.py",
    "statusd_eye.py",
    "statusd_sessions.py",
    "statusd_privacy.py",
    "statusd_command_cache.py",
    "ttl_cache.py",
    "jsonl_tail.py",
    "codex_hooks.py",
    "bootstrap_cli.py",
]

PLIST_NAMES = [
    "com.phenotype.agent-user-statusd.plist",
    "com.phenotype.agent-user-status-tray.plist",
    "com.phenotype.agent-user-status-cursor-tracker.plist",
    "com.phenotype.agent-user-status-webcam-eye-tracker.plist",
]

RUNTIME_BIN_SPECS = [
    ("agent-imessage", "agent_user_status/agent_imessage.py"),
    ("agent-user-statusd", "agent_user_status/statusd.py"),
    ("agent-user-status-cursor-tracker", "agent_user_status/cursor_tracker.py"),
    ("agent-user-status-webcam-eye-tracker", "agent_user_status/webcam_eye_tracker.py"),
    ("agent-imessage-mcp", "mcp/agent_imessage_mcp.py"),
]

NATIVE_MONITOR_FILES = [
    "AgentUserStatusMonitor.swift",
    "AgentUserStatusApp.swift",
    "CalibrationEvalController.swift",
    "AgentSessions.swift",
    "CalibrationEvalStats.swift",
    "DotOverlayView.swift",
    "EyeTrackerControls.swift",
    "MonitorStatusSummary.swift",
    "MonitorUIStateStore.swift",
    "NativeRuntimePaths.swift",
    "WorkspaceAttribution.swift",
    "VisualGazeFilter.swift",
    "WindowTracking.swift",
    "PanelView.swift",
    "StatusModel.swift",
]

NATIVE_APP_NAME = "Agent User Status.app"
NATIVE_APP_EXECUTABLE = "AgentUserStatusMonitor"


def env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser() if value else default


def runtime_bin_dir() -> Path:
    return env_path("AGENT_USER_STATUS_BIN_DIR", Path.home() / ".local" / "bin")


def runtime_bin_path(executable: str, override_env: str | None = None) -> Path:
    if override_env:
        override = os.environ.get(override_env)
        if override:
            return Path(override).expanduser()
    return runtime_bin_dir() / executable


def agent_imessage_bin() -> Path:
    return runtime_bin_path("agent-imessage", "AGENT_IMESSAGE_BIN")


def imsg_bin() -> Path:
    return runtime_bin_path("imsg", "IMSG_BIN")


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value not in {"0", "false", "False", "no", "NO"}


def locate_source_root() -> Path:
    override = os.environ.get("AGENT_USER_STATUS_SOURCE_ROOT")
    if override:
        root = Path(override).expanduser().resolve()
        if (root / "src" / "agent_user_status").exists():
            return root

    here = Path(__file__).resolve()
    for candidate in [Path.cwd(), *Path.cwd().parents, here.parent, *here.parents]:
        root = candidate.resolve()
        if (
            (root / "src" / "agent_user_status").exists()
            and (root / "scripts" / "install.sh").exists()
        ):
            return root

    raise SystemExit("Could not locate the source checkout. Set AGENT_USER_STATUS_SOURCE_ROOT.")


def resolve_paths() -> BootstrapPaths:
    root = locate_source_root()
    share_dir = env_path(
        "AGENT_USER_STATUS_SHARE_DIR",
        Path.home() / ".local" / "share" / "agent-imessage",
    )
    return BootstrapPaths(
        root=root,
        src=root / "src",
        launchd_src=root / "launchd",
        bin_dir=runtime_bin_dir(),
        share_dir=share_dir,
        launchd_dir=env_path(
            "AGENT_USER_STATUS_LAUNCHD_DIR",
            Path.home() / "Library" / "LaunchAgents",
        ),
        state_dir=env_path("AGENT_IMESSAGE_STATE_DIR", share_dir / "state"),
        eye_venv=env_path(
            "AGENT_USER_STATUS_EYE_VENV",
            Path.home() / ".local" / "share" / "agent-imessage" / "eye-tracker-venv",
        ),
    )


def source_runtime_paths(paths: Any) -> list[Path]:
    root = paths.src
    return [
        root / source for _, source in RUNTIME_BIN_SPECS
    ] + [
        root / "agent_user_status" / "bootstrap.py",
        root / "agent_user_status" / "bootstrap_cli.py",
    ]


def installed_runtime_paths(paths: Any) -> list[Path]:
    bin_dir = paths.bin_dir
    return [bin_dir / name for name, _ in RUNTIME_BIN_SPECS] + [bin_dir / "agent-user-status"]


def installed_support_paths(paths: Any) -> list[Path]:
    bin_dir = paths.bin_dir
    return [bin_dir / "agent_user_status" / "__init__.py"] + [
        bin_dir / "agent_user_status" / filename for filename in SUPPORT_MODULES
    ]


def native_monitor_paths(paths: Any) -> list[Path]:
    share_dir = paths.share_dir
    return [share_dir / "native-monitor" / filename for filename in NATIVE_MONITOR_FILES]


def native_app_bundle(paths: Any) -> Path:
    return paths.share_dir / NATIVE_APP_NAME


def native_app_executable(paths: Any) -> Path:
    return native_app_bundle(paths) / "Contents" / "MacOS" / NATIVE_APP_EXECUTABLE


def native_app_paths(paths: Any) -> list[Path]:
    app = native_app_bundle(paths)
    return [
        app / "Contents" / "Info.plist",
        native_app_executable(paths),
    ]


def runtime_paths_metadata(paths: BootstrapPaths, python_bin: Path, eye_python_bin: Path) -> dict[str, str]:
    """Return install metadata consumed by native controls and diagnostics."""
    return {
        "bin_dir": str(paths.bin_dir),
        "share_dir": str(paths.share_dir),
        "state_dir": str(paths.state_dir),
        "launchd_dir": str(paths.launchd_dir),
        "python_bin": str(python_bin),
        "eye_python_bin": str(eye_python_bin),
        "webcam_eye_tracker_bin": str(paths.bin_dir / "agent-user-status-webcam-eye-tracker"),
        "native_monitor_bin": str(native_app_executable(paths)),
        "eye_calibration_path": str(paths.state_dir / "eye_calibration.json"),
    }
