"""Eye-tracker environment setup for the agent-user-status bootstrap CLI."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from agent_user_status.bootstrap_runtime import detect_python
from agent_user_status.bootstrap_support import resolve_paths


def setup_eye_tracker_command(_: argparse.Namespace) -> int:
    if sys.platform != "darwin":
        raise SystemExit("webcam eye-tracker setup is currently supported only on macOS")

    paths = resolve_paths()
    default_bootstrap = shutil.which("python3.11") or str(detect_python())
    eye_bootstrap_python = Path(
        os.environ.get("AGENT_USER_STATUS_EYE_BOOTSTRAP_PYTHON", default_bootstrap)
    ).expanduser()
    if not eye_bootstrap_python.exists():
        raise SystemExit(
            f"missing Python 3.11 at {eye_bootstrap_python}\n"
            "install python@3.11 or set AGENT_USER_STATUS_EYE_BOOTSTRAP_PYTHON"
        )

    if shutil.which("uv"):
        subprocess.run(["uv", "venv", "--python", str(eye_bootstrap_python), str(paths.eye_venv)], check=True)
    else:
        subprocess.run([str(eye_bootstrap_python), "-m", "venv", str(paths.eye_venv)], check=True)

    eye_python = paths.eye_venv / "bin" / "python"
    subprocess.run([str(eye_python), "-m", "ensurepip", "--upgrade"], check=True)
    subprocess.run([str(eye_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run(
        [
            str(eye_python),
            "-m",
            "pip",
            "install",
            "mediapipe>=0.10.30",
            "opencv-python>=4.10",
            "numpy>=1.26",
            "pyobjc-framework-Cocoa>=10.0",
        ],
        check=True,
    )

    env = os.environ.copy()
    env["AGENT_USER_STATUS_SOURCE_ROOT"] = str(paths.root)
    env["AGENT_USER_STATUS_EYE_PYTHON_BIN"] = str(eye_python)
    env["PYTHONPATH"] = (
        f"{paths.root / 'src'}{os.pathsep}{env['PYTHONPATH']}" if env.get("PYTHONPATH") else str(paths.root / "src")
    )
    subprocess.run(
        [str(eye_python), "-m", "agent_user_status.bootstrap", "install"],
        env=env,
        cwd=str(paths.root),
        check=True,
    )
    subprocess.run([str(eye_python), str(paths.bin_dir / "agent-user-status-webcam-eye-tracker"), "check"], check=True)

    print("Eye tracker runtime is installed.")
    print(f"If camera access is denied, grant Camera permission to:\n  {eye_python}")
    print("Calibrate when ready:")
    print(f"  {eye_python} {paths.bin_dir / 'agent-user-status-webcam-eye-tracker'} calibrate")
    print("Evaluate calibration:")
    print(f"  {eye_python} {paths.bin_dir / 'agent-user-status-webcam-eye-tracker'} evaluate")
    print("Start calibrated tracker:")
    print("  launchctl kickstart -k gui/$(id -u)/com.phenotype.agent-user-status-webcam-eye-tracker")
    return 0
