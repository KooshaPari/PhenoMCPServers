from __future__ import annotations

import os
import plistlib
import shutil
import stat
import subprocess
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STAGE_SCRIPT = ROOT / "packaging" / "scripts" / "stage-macos-payload.sh"
BUILD_SCRIPT = ROOT / "packaging" / "scripts" / "build-macos-pkg.sh"
BUILD_TEST_ROOT = ROOT / "build" / "pytest-packaging"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def make_executable(path: Path, text: str = "#!/usr/bin/env bash\nexit 0\n") -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def packaging_workspace(tmp_path: Path) -> Iterator[dict[str, Path]]:
    shutil.rmtree(BUILD_TEST_ROOT, ignore_errors=True)
    app = tmp_path / "Agent User Status.app"
    contents = app / "Contents"
    macos = contents / "MacOS"
    macos.mkdir(parents=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    (contents / "Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleIdentifier": "com.phenotype.agent-user-status",
                "CFBundleShortVersionString": project["version"],
            }
        )
    )
    make_executable(macos / "AgentUserStatusMonitor")

    bin_dir = tmp_path / "bin"
    support = bin_dir / "agent_user_status"
    support.mkdir(parents=True)
    for binary in ("agent-user-status", "agent-imessage", "agent-user-statusd"):
        make_executable(bin_dir / binary)
    (support / "agent_imessage_envelope.py").write_text("# support module\n", encoding="utf-8")

    yield {"app": app, "bin": bin_dir, "payload": BUILD_TEST_ROOT / "payload"}
    shutil.rmtree(BUILD_TEST_ROOT, ignore_errors=True)


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_stage_macos_payload_dry_run_prints_actions_without_writing(
    packaging_workspace: dict[str, Path],
) -> None:
    payload = packaging_workspace["payload"]

    result = run_script(
        str(STAGE_SCRIPT),
        "--dry-run",
        "--payload-root",
        str(payload),
        "--app-source",
        str(packaging_workspace["app"]),
        "--bin-source",
        str(packaging_workspace["bin"]),
    )

    assert result.returncode == 0, result.stderr
    assert "[macos-stage] mode: dry-run" in result.stdout
    assert "cp -R" in result.stdout
    assert "Agent\\ User\\ Status.app" in result.stdout
    assert not payload.exists()


@pytest.mark.parametrize(
    "payload_root",
    [
        "/",
        str(Path.home()),
        str(Path.home() / ".local"),
        str(Path(os.environ.get("TMPDIR", "/tmp")) / "agent-user-status-payload"),
    ],
)
@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_stage_macos_payload_rejects_unsafe_payload_roots(
    packaging_workspace: dict[str, Path],
    payload_root: str,
) -> None:
    result = run_script(
        str(STAGE_SCRIPT),
        "--dry-run",
        "--payload-root",
        payload_root,
        "--app-source",
        str(packaging_workspace["app"]),
        "--bin-source",
        str(packaging_workspace["bin"]),
    )

    assert result.returncode != 0
    assert "refusing to stage into" in result.stderr or "payload root must stay under" in result.stderr


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_build_macos_pkg_dry_run_prints_stage_and_build_commands(tmp_path: Path) -> None:
    payload = BUILD_TEST_ROOT / "missing-payload"
    work_dir = BUILD_TEST_ROOT / "work"
    output = tmp_path / "AgentUserStatus.pkg"

    result = run_script(
        str(BUILD_SCRIPT),
        "--dry-run",
        "--payload-root",
        str(payload),
        "--work-dir",
        str(work_dir),
        "--output",
        str(output),
    )

    assert result.returncode == 0, result.stderr
    assert "payload root is not staged yet" in result.stdout
    assert "stage-macos-payload.sh" in result.stdout
    assert "pkgbuild" in result.stdout
    assert "productbuild" in result.stdout
    assert not work_dir.exists()


@pytest.mark.requirement("FR-AGENT_USER_STATUS-009")
def test_build_macos_pkg_dry_run_rejects_malformed_payload() -> None:
    payload = BUILD_TEST_ROOT / "bad-payload"
    app_contents = payload / "Applications" / "Agent User Status.app" / "Contents"
    app_contents.mkdir(parents=True, exist_ok=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    (app_contents / "Info.plist").write_bytes(
        plistlib.dumps(
            {
                "CFBundleIdentifier": "com.phenotype.agent-user-status",
                "CFBundleShortVersionString": project["version"],
            }
        )
    )

    result = run_script(str(BUILD_SCRIPT), "--dry-run", "--payload-root", str(payload))

    assert result.returncode != 0
    assert "payload missing executable monitor" in result.stderr
