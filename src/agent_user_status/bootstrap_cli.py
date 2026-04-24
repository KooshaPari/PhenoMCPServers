#!/usr/bin/env python3
"""Packaging and runtime bootstrap CLI for agent-user-status."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

from agent_user_status.bootstrap_native import install_native_monitor
from agent_user_status.bootstrap_support import (
    PLIST_NAMES,
    SUPPORT_MODULES,
    BootstrapPaths,
    env_bool,
    installed_runtime_paths,
    installed_support_paths,
    native_app_bundle,
    native_app_executable,
    native_app_paths,
    native_monitor_paths,
    resolve_paths,
    source_runtime_paths,
)


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


def install_bootstrap_wrapper(paths: BootstrapPaths, python_bin: Path) -> None:
    wrapper = f"""#!/usr/bin/env sh
set -eu
export AGENT_USER_STATUS_SOURCE_ROOT={shlex.quote(str(paths.root))}
export PYTHONPATH={shlex.quote(str(paths.bin_dir))}${{PYTHONPATH:+:$PYTHONPATH}}
exec {shlex.quote(str(python_bin))} -m agent_user_status.bootstrap "$@"
"""
    write_text_file(paths.bin_dir / "agent-user-status", wrapper)


def install_python_support_modules(paths: BootstrapPaths) -> None:
    module_dir = paths.bin_dir / "agent_user_status"
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text("", encoding="utf-8")
    for filename in SUPPORT_MODULES:
        shutil.copy2(paths.src / "agent_user_status" / filename, module_dir / filename)


def replace_template(template: Path, output: Path, replacements: dict[str, str]) -> None:
    source = template.read_text(encoding="utf-8")
    for key, value in replacements.items():
        source = source.replace(key, value)
    if "{{" in source:
        raise SystemExit(f"unresolved launchd template tokens remain in {template.name}")
    output.write_text(source, encoding="utf-8")


def launchd_path(paths: BootstrapPaths, python_bin: Path) -> str:
    python_bin_dir = str(python_bin.resolve().parent)
    return f"{python_bin_dir}:{paths.bin_dir}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def install_launchd_plists(paths: BootstrapPaths, python_bin: Path, eye_python_bin: Path, start_services: bool) -> None:
    uid = str(os.getuid())
    template_count = 0
    for name in PLIST_NAMES:
        template = paths.launchd_src / name
        if not template.exists():
            continue
        template_count += 1
        installed = paths.launchd_dir / name
        generated = paths.share_dir / f".{name}.tmp"
        replacements = {
            "{{PYTHON_BIN}}": str(python_bin),
            "{{EYE_PYTHON_BIN}}": str(eye_python_bin),
            "{{AGENT_USER_STATUSD_BIN}}": str(paths.bin_dir / "agent-user-statusd"),
            "{{AGENT_USER_STATUS_CURSOR_TRACKER}}": str(paths.bin_dir / "agent-user-status-cursor-tracker"),
            "{{AGENT_USER_STATUS_WEBCAM_EYE_TRACKER}}": str(paths.bin_dir / "agent-user-status-webcam-eye-tracker"),
            "{{AGENT_USER_STATUS_NATIVE_MONITOR}}": str(native_app_executable(paths)),
            "{{STATE_DIR}}": str(paths.state_dir),
            "{{LAUNCHD_PATH}}": launchd_path(paths, python_bin),
        }
        replace_template(template, generated, replacements)
        shutil.copy2(generated, installed)
        generated.unlink(missing_ok=True)

        if not start_services or sys.platform != "darwin" or not shutil.which("launchctl"):
            continue

        subprocess.run(
            ["launchctl", "bootout", f"gui/{uid}", str(installed)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(installed)], check=False).returncode != 0:
            log("warn", f"could not bootstrap {name}. Inspect {installed}.")
            continue

        run_at_load = subprocess.run(
            ["plutil", "-extract", "RunAtLoad", "raw", "-o", "-", str(installed)],
            capture_output=True,
            text=True,
            check=False,
        )
        if run_at_load.stdout.strip() == "true":
            label = name.removesuffix(".plist")
            subprocess.run(
                ["launchctl", "kickstart", "-k", f"gui/{uid}/{label}"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    if template_count == 0:
        log("warn", f"no LaunchAgent templates found in {paths.launchd_src}.")


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


def install_command(args: argparse.Namespace) -> int:
    paths = resolve_paths()
    ensure_directories(paths)
    python_bin = detect_python()
    eye_python_bin = default_eye_python(paths, python_bin)
    start_services = env_bool("AGENT_USER_STATUS_START_SERVICES", True) and not args.no_start
    strict = env_bool("AGENT_USER_STATUS_STRICT", True)

    install_executable(paths.src / "agent_user_status" / "agent_imessage.py", paths.bin_dir / "agent-imessage")
    install_executable(paths.src / "agent_user_status" / "statusd.py", paths.bin_dir / "agent-user-statusd")
    install_executable(
        paths.src / "agent_user_status" / "cursor_tracker.py",
        paths.bin_dir / "agent-user-status-cursor-tracker",
    )
    install_executable(
        paths.src / "agent_user_status" / "webcam_eye_tracker.py",
        paths.bin_dir / "agent-user-status-webcam-eye-tracker",
    )
    install_executable(paths.src / "mcp" / "agent_imessage_mcp.py", paths.bin_dir / "agent-imessage-mcp")
    install_bootstrap_wrapper(paths, python_bin)
    install_python_support_modules(paths)
    install_native_monitor(paths, log)
    install_launchd_plists(paths, python_bin, eye_python_bin, start_services=start_services)
    if not start_services:
        log("info", "installed launch agents; set AGENT_USER_STATUS_START_SERVICES=1 to auto-start.")
    elif sys.platform != "darwin":
        log("info", "installed launch agents; launch services are available only on macOS.")
    else:
        log("info", "installed launch agents and attempted service startup.")
    log("info", f"native monitor sources: {paths.share_dir / 'native-monitor'}")
    if strict:
        return doctor_command(argparse.Namespace())
    return 0


def uninstall_command(args: argparse.Namespace) -> int:
    paths = resolve_paths()
    bin_targets = installed_runtime_paths(paths)
    plist_targets = [paths.launchd_dir / name for name in PLIST_NAMES]

    if sys.platform == "darwin" and shutil.which("launchctl"):
        uid = str(os.getuid())
        for plist in plist_targets:
            if plist.exists():
                subprocess.run(
                    ["launchctl", "bootout", f"gui/{uid}", str(plist)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

    if not args.no_remove:
        for path in bin_targets:
            remove_path(path, args.dry_run)
        for path in plist_targets:
            remove_path(path, args.dry_run)
        for path in [
            *native_monitor_paths(paths),
            *native_app_paths(paths),
            *installed_support_paths(paths),
        ]:
            remove_path(path, args.dry_run)
        remove_dir(paths.bin_dir / "agent_user_status", args.dry_run)
        remove_dir(paths.share_dir / "native-monitor", args.dry_run)
        remove_dir(native_app_bundle(paths), args.dry_run)
    else:
        print("Skipping file removal because --no-remove was set.")

    if args.purge:
        remove_dir(paths.state_dir, args.dry_run)

    if args.purge:
        print("uninstall complete (services stopped, files removed, state purged).")
    else:
        print("uninstall complete (services stopped, files removed; state preserved).")
    return 0


def py_compile_command(paths: BootstrapPaths) -> int:
    result = subprocess.run([sys.executable, "-m", "py_compile", *map(str, source_runtime_paths(paths))], check=False)
    return result.returncode


def doctor_command(_: argparse.Namespace) -> int:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-user-status",
        description="Packaging and runtime bootstrap for agent-user-status",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install runtime bins, plist files, and native monitor")
    install.add_argument("--no-start", action="store_true", help="Install without starting launchd jobs")
    install.set_defaults(handler=install_command)

    uninstall = subparsers.add_parser("uninstall", help="Stop services and remove installed files")
    uninstall.add_argument("--purge", action="store_true", help="Remove state and logs")
    uninstall.add_argument("--no-remove", action="store_true", help="Stop services only")
    uninstall.add_argument("--dry-run", action="store_true", help="Print planned removals without changing files")
    uninstall.set_defaults(handler=uninstall_command)

    doctor = subparsers.add_parser("doctor", help="Validate local packaging and runtime layout")
    doctor.set_defaults(handler=doctor_command)

    setup = subparsers.add_parser("setup-eye-tracker", help="Provision the eye-tracker venv and install runtime")
    setup.set_defaults(handler=setup_eye_tracker_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
