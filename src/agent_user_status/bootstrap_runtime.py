"""Runtime helpers for the agent-user-status bootstrap CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from agent_user_status.bootstrap_support import BootstrapPaths


def log(level: str, message: str) -> None:
    print(f"[{level}] {message}")


def detect_python() -> Path:
    override = os.environ.get("AGENT_USER_STATUS_PYTHON_BIN")
    if override:
        return Path(override).expanduser()

    candidates = [
        Path(sys.executable),
        Path.home() / ".local" / "bin" / "python3",
        Path("/opt/homebrew/bin/python3"),
        Path("/usr/bin/python3"),
        Path("/usr/local/bin/python3"),
    ]
    for candidate in candidates:
        resolved = shutil.which(str(candidate))
        if resolved and subprocess.run(
            [resolved, "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0:
            return Path(resolved)

    resolved = shutil.which("python3")
    if resolved and subprocess.run(
        [resolved, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    ).returncode == 0:
        return Path(resolved)

    raise SystemExit("Python 3 was not found. Set AGENT_USER_STATUS_PYTHON_BIN.")


def default_eye_python(paths: BootstrapPaths, python_bin: Path) -> Path:
    override = os.environ.get("AGENT_USER_STATUS_EYE_PYTHON_BIN")
    if override:
        return Path(override).expanduser()

    eye_python = paths.eye_venv / "bin" / "python"
    return eye_python if eye_python.exists() else python_bin


def ensure_directories(paths: BootstrapPaths) -> None:
    paths.bin_dir.mkdir(parents=True, exist_ok=True)
    paths.share_dir.mkdir(parents=True, exist_ok=True)
    paths.launchd_dir.mkdir(parents=True, exist_ok=True)
    paths.state_dir.mkdir(parents=True, exist_ok=True)


def install_executable(src: Path, dst: Path) -> None:
    shutil.copy2(src, dst)
    dst.chmod(0o700)


def write_text_file(path: Path, content: str, mode: int = 0o700) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def remove_path(path: Path, dry_run: bool) -> None:
    if not path.exists():
        return
    if dry_run:
        print(f"[dry-run] rm -f {path}")
        return
    path.unlink()


def remove_dir(path: Path, dry_run: bool) -> None:
    if not path.exists():
        return
    if dry_run:
        print(f"[dry-run] rm -rf {path}")
        return
    shutil.rmtree(path, ignore_errors=True)
