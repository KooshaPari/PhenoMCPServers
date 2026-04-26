#!/usr/bin/env bash

validate_payload_contents() {
  local root="$1"
  local app="$root/Applications/Agent User Status.app"
  local monitor="$app/Contents/MacOS/AgentUserStatusMonitor"
  local info="$app/Contents/Info.plist"
  local binary

  [[ -d "$root" ]] || fail "payload root does not exist: $root"
  [[ -d "$app" ]] || fail "payload missing app bundle: $app"
  [[ -f "$info" ]] || fail "payload missing app Info.plist: $info"
  [[ -x "$monitor" ]] || fail "payload missing executable monitor: $monitor"

  for binary in agent-user-status agent-imessage agent-user-statusd; do
    [[ -x "$root/usr/local/bin/$binary" ]] || fail "payload missing executable: /usr/local/bin/$binary"
  done
  [[ -d "$root/usr/local/bin/agent_user_status" ]] || \
    fail "payload missing Python support modules: /usr/local/bin/agent_user_status"
  [[ -f "$root/usr/local/bin/agent_user_status/agent_imessage_envelope.py" ]] || \
    fail "payload missing support module: agent_imessage_envelope.py"

  if command -v plutil >/dev/null 2>&1; then
    plutil -lint "$info" >/dev/null
  fi

  python3 - "$ROOT" "$info" <<'PY'
import plistlib
import sys
import tomllib
from pathlib import Path

root = Path(sys.argv[1])
info_path = Path(sys.argv[2])
project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
info = plistlib.loads(info_path.read_bytes())
if info["CFBundleIdentifier"] != "com.phenotype.agent-user-status":
    raise SystemExit(f"payload app bundle id mismatch: {info['CFBundleIdentifier']}")
if info["CFBundleShortVersionString"] != project["version"]:
    raise SystemExit("payload app version does not match pyproject")
PY
}

metadata_value() {
  local key="$1"
  python3 - "$ROOT" "$key" <<'PY'
import plistlib
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(sys.argv[1])
key = sys.argv[2]
pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
info = plistlib.loads((root / "packaging/macos/Info.plist").read_bytes())
dist = ET.parse(root / "packaging/macos/pkg/Distribution.xml").getroot()

pkg_refs = [
    elem for elem in dist.findall("pkg-ref")
    if elem.attrib.get("id") == "com.phenotype.agent-user-status.pkg"
]
versioned_pkg_refs = [elem for elem in pkg_refs if "version" in elem.attrib]
if not versioned_pkg_refs:
    raise SystemExit("Distribution.xml has no versioned pkg-ref for component package")

values = {
    "project_version": pyproject["project"]["version"],
    "bundle_version": info["CFBundleShortVersionString"],
    "bundle_id": info["CFBundleIdentifier"],
    "distribution_version": versioned_pkg_refs[0].attrib["version"],
    "distribution_pkg_filename": (versioned_pkg_refs[0].text or "").strip(),
}

if key == "validate":
    errors = []
    if values["bundle_id"] != "com.phenotype.agent-user-status":
        errors.append(f"unexpected bundle id: {values['bundle_id']}")
    if values["project_version"] != values["bundle_version"]:
        errors.append(
            "pyproject version does not match Info.plist "
            f"({values['project_version']} != {values['bundle_version']})"
        )
    if values["project_version"] != values["distribution_version"]:
        errors.append(
            "pyproject version does not match Distribution.xml "
            f"({values['project_version']} != {values['distribution_version']})"
        )
    if values["distribution_pkg_filename"] != "agent-user-status.pkg":
        errors.append(
            "Distribution.xml must reference component package "
            f"agent-user-status.pkg, got {values['distribution_pkg_filename']!r}"
        )
    if not re.fullmatch(r"\d+(?:\.\d+){0,3}(?:[-+][A-Za-z0-9_.-]+)?", values["project_version"]):
        errors.append(f"unsupported package version: {values['project_version']}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(values["project_version"])
else:
    print(values[key])
PY
}
