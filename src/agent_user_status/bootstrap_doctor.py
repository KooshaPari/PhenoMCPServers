"""Doctor checks for the agent-user-status bootstrap CLI."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

from agent_user_status.bootstrap_support import (
    PLIST_NAMES,
    BootstrapPaths,
    installed_runtime_paths,
    installed_support_paths,
    native_app_paths,
    native_monitor_paths,
    resolve_paths,
    source_runtime_paths,
)

BOOTSTRAP_HELPER_MODULES = [
    "bootstrap_runtime.py",
    "bootstrap_doctor.py",
    "bootstrap_eye_setup.py",
]


def source_bootstrap_helper_paths(paths: BootstrapPaths) -> list[Path]:
    return [paths.src / "agent_user_status" / filename for filename in BOOTSTRAP_HELPER_MODULES]


def installed_bootstrap_helper_paths(paths: BootstrapPaths) -> list[Path]:
    return [paths.bin_dir / "agent_user_status" / filename for filename in BOOTSTRAP_HELPER_MODULES]


def py_compile_command(paths: BootstrapPaths) -> int:
    sources = [*source_runtime_paths(paths), *source_bootstrap_helper_paths(paths)]
    result = subprocess.run([sys.executable, "-m", "py_compile", *map(str, sources)], check=False)
    return result.returncode


def doctor_command(_: object) -> int:
    paths = resolve_paths()
    ok = True

    def check(name: str, callback: Callable[[], None]) -> None:
        nonlocal ok
        try:
            callback()
        except Exception as exc:  # noqa: BLE001
            print(f"fail {name}")
            print(str(exc))
            ok = False
        else:
            print(f"ok   {name}")

    def check_python() -> None:
        if py_compile_command(paths) != 0:
            raise RuntimeError("python syntax")

    def check_swift() -> None:
        command = [
            "swiftc",
            *map(str, sorted((paths.src / "native" / "macos").glob("*.swift"))),
            "-o",
            str(Path(tempfile.gettempdir()) / "agent-user-status-native-monitor"),
            "-framework",
            "AppKit",
            "-framework",
            "CoreGraphics",
        ]
        if subprocess.run(command, check=False).returncode != 0:
            raise RuntimeError("swift compile")

    def check_layout() -> None:
        required = [
            *installed_runtime_paths(paths),
            *installed_support_paths(paths),
            *installed_bootstrap_helper_paths(paths),
            *native_monitor_paths(paths),
            *native_app_paths(paths),
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise RuntimeError("installed runtime layout\n" + "\n".join(missing[:12]))

    def check_plists() -> None:
        for plist in paths.launchd_src.glob("*.plist"):
            if subprocess.run(["plutil", "-lint", str(plist)], check=False).returncode != 0:
                raise RuntimeError(f"plist {plist.name}")
        missing = []
        unresolved = []
        for name in PLIST_NAMES:
            installed = paths.launchd_dir / name
            if not installed.exists():
                missing.append(str(installed))
                continue
            if subprocess.run(["plutil", "-lint", str(installed)], check=False).returncode != 0:
                raise RuntimeError(f"installed plist {name}")
            if "{{" in installed.read_text(encoding="utf-8"):
                unresolved.append(str(installed))
        if missing:
            raise RuntimeError("installed plists missing\n" + "\n".join(missing))
        if unresolved:
            raise RuntimeError("installed plists contain unresolved tokens\n" + "\n".join(unresolved))

    def check_backend() -> None:
        with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=5) as response:
            if response.status != 200:
                raise RuntimeError("backend health")

    check("python syntax", check_python)
    if sys.platform == "darwin":
        check("swift compile", check_swift)
    else:
        print("skip swift compile (macOS only)")
    check("installed runtime layout", check_layout)
    if sys.platform == "darwin":
        check("plists", check_plists)
    else:
        print("skip plists (macOS only)")
    if shutil.which("curl"):
        check("backend health", check_backend)
    if ok:
        print("doctor passed")
        return 0
    return 1
