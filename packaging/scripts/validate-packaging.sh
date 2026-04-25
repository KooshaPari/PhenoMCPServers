#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="all"

usage() {
  cat <<'EOF'
Usage:
  packaging/scripts/validate-packaging.sh [all|macos|linux|windows]

Validates packaging metadata without building or installing platform packages.
Native validators are used when present; Python fallback checks keep CI useful
on hosts that do not have platform SDKs installed.
EOF
}

log() {
  printf '[packaging-validate] %s\n' "$*"
}

fail() {
  printf '[packaging-validate] error: %s\n' "$*" >&2
  exit 1
}

python_validate() {
  python3 - "$ROOT" "$1" <<'PY'
import configparser
import plistlib
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(sys.argv[1])
target = sys.argv[2]
project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
version = project["version"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def validate_macos() -> None:
    info = plistlib.loads((root / "packaging/macos/Info.plist").read_bytes())
    entitlements = plistlib.loads((root / "packaging/macos/entitlements.plist").read_bytes())
    dist = ET.parse(root / "packaging/macos/pkg/Distribution.xml").getroot()
    pkg_refs = [
        elem for elem in dist.findall("pkg-ref")
        if elem.attrib.get("id") == "com.phenotype.agent-user-status.pkg"
    ]
    versioned_pkg_refs = [elem for elem in pkg_refs if "version" in elem.attrib]

    require(info["CFBundleIdentifier"] == "com.phenotype.agent-user-status", "unexpected macOS bundle id")
    require(info["CFBundleShortVersionString"] == version, "macOS Info.plist version drift")
    require(info["CFBundlePackageType"] == "APPL", "macOS bundle package type must be APPL")
    require(bool(info.get("LSUIElement")), "macOS app must remain a menu-bar app")
    require("NSCameraUsageDescription" in info, "macOS camera privacy description is required")
    require(bool(versioned_pkg_refs), "Distribution.xml needs a versioned component pkg-ref")
    require(versioned_pkg_refs[0].attrib["version"] == version, "Distribution.xml version drift")
    require((versioned_pkg_refs[0].text or "").strip() == "agent-user-status.pkg", "bad component pkg filename")
    require(
        entitlements.get("com.apple.security.device.camera") is True,
        "camera entitlement must stay explicit for opt-in native calibration",
    )


def validate_linux() -> None:
    desktop_path = root / "packaging/linux/agent-user-status.desktop"
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    parser.read(desktop_path, encoding="utf-8")
    require(parser.has_section("Desktop Entry"), "desktop file missing Desktop Entry section")
    entry = parser["Desktop Entry"]
    require(entry.get("Type") == "Application", "desktop Type must be Application")
    require(entry.get("Exec") == "agent-user-status", "desktop Exec must use packaged CLI")
    require(entry.get("Terminal") == "false", "desktop Terminal must be false")
    require("Development" in entry.get("Categories", ""), "desktop Categories must include Development")

    meta = ET.parse(root / "packaging/linux/com.phenotype.AgentUserStatus.metainfo.xml").getroot()
    require(meta.attrib.get("type") == "desktop-application", "AppStream component type mismatch")
    require(meta.findtext("id") == "com.phenotype.AgentUserStatus", "AppStream id mismatch")
    require(meta.find("launchable").text == "agent-user-status.desktop", "AppStream launchable mismatch")
    release = meta.find("releases/release")
    require(release is not None, "AppStream release metadata is required")
    require(release.attrib.get("version") == version, "AppStream version drift")


def validate_windows() -> None:
    manifest = ET.parse(root / "packaging/windows/msix/AppxManifest.xml").getroot()
    ns = {
        "m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
        "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
        "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
    }
    identity = manifest.find("m:Identity", ns)
    require(identity is not None, "MSIX Identity is required")
    require(identity.attrib.get("Name") == "Phenotype.AgentUserStatus", "MSIX package name mismatch")
    require(re.fullmatch(r"\d+\.\d+\.\d+\.\d+", identity.attrib.get("Version", "")) is not None, "MSIX version must have four numeric segments")
    require(identity.attrib.get("Version") == f"{version}.0", "MSIX version drift")
    application = manifest.find("m:Applications/m:Application", ns)
    require(application is not None, "MSIX Application is required")
    require(
        application.attrib.get("Executable") == r"VFS\ProgramFilesX64\AgentUserStatus\agent-user-status.exe",
        "MSIX executable path mismatch",
    )
    capability = manifest.find("m:Capabilities/rescap:Capability[@Name='runFullTrust']", ns)
    require(capability is not None, "MSIX runFullTrust capability must be explicit")


if target in {"macos", "all"}:
    validate_macos()
if target in {"linux", "all"}:
    validate_linux()
if target in {"windows", "all"}:
    validate_windows()
PY
}

validate_macos() {
  log "macOS metadata"
  if command -v plutil >/dev/null 2>&1; then
    plutil -lint "${ROOT}/packaging/macos/Info.plist" >/dev/null
    plutil -lint "${ROOT}/packaging/macos/entitlements.plist" >/dev/null
  else
    log "plutil not found; using Python plist parser"
  fi
  if command -v xmllint >/dev/null 2>&1; then
    xmllint --noout "${ROOT}/packaging/macos/pkg/Distribution.xml"
  else
    log "xmllint not found; using Python XML parser"
  fi
  python_validate macos
}

validate_linux() {
  log "Linux desktop/AppStream metadata"
  if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "${ROOT}/packaging/linux/agent-user-status.desktop"
  else
    log "desktop-file-validate not found; using Python desktop-entry checks"
  fi
  if command -v appstreamcli >/dev/null 2>&1; then
    appstreamcli validate --no-net "${ROOT}/packaging/linux/com.phenotype.AgentUserStatus.metainfo.xml"
  else
    log "appstreamcli not found; using Python AppStream checks"
  fi
  python_validate linux
}

validate_windows() {
  log "Windows MSIX manifest"
  if command -v xmllint >/dev/null 2>&1; then
    xmllint --noout "${ROOT}/packaging/windows/msix/AppxManifest.xml"
  else
    log "xmllint not found; using Python XML parser"
  fi
  python_validate windows
}

if [[ $# -gt 1 ]]; then
  usage
  exit 2
fi
if [[ $# -eq 1 ]]; then
  MODE="$1"
fi

command -v python3 >/dev/null 2>&1 || fail "missing required tool: python3"

case "$MODE" in
  all)
    validate_macos
    validate_linux
    validate_windows
    ;;
  macos)
    validate_macos
    ;;
  linux)
    validate_linux
    ;;
  windows)
    validate_windows
    ;;
  -h | --help)
    usage
    ;;
  *)
    fail "unknown target: $MODE"
    ;;
esac

log "ok"
