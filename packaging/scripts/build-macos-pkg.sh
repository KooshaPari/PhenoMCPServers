#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PACKAGE_NAME="Agent User Status"
PACKAGE_ID="com.phenotype.agent-user-status.pkg"
APP_ID="com.phenotype.agent-user-status"

MODE="dry-run"
WORK_DIR="${ROOT}/build/pkg/macos"
PAYLOAD_ROOT="${ROOT}/build/pkg/macos/payload"
OUTPUT=""
VERSION=""
KEEP_WORK=0

usage() {
  cat <<'EOF'
Usage:
  packaging/scripts/build-macos-pkg.sh [options]

Options:
  --dry-run              Validate metadata and print the build commands. Default.
  --build                Build the component package and product archive.
  --payload-root PATH    Staged package root. Default: build/pkg/macos/payload
  --work-dir PATH        Build scratch directory. Default: build/pkg/macos
  --output PATH          Product archive path. Default: build/pkg/macos/AgentUserStatus-<version>.pkg
  --version VERSION      Override package version after metadata validation.
  --keep-work            Do not delete intermediate component package.
  -h, --help             Show this help.

Signing and notarization are opt-in through environment variables:
  AGENT_USER_STATUS_PKG_SIGN_IDENTITY       Optional pkgbuild signing identity.
  AGENT_USER_STATUS_PRODUCT_SIGN_IDENTITY   Optional productbuild signing identity.
  AGENT_USER_STATUS_NOTARY_PROFILE          Optional notarytool keychain profile.
  AGENT_USER_STATUS_NOTARY_APPLE_ID         Optional Apple ID for notarytool.
  AGENT_USER_STATUS_NOTARY_PASSWORD         Optional app-specific password.
  AGENT_USER_STATUS_NOTARY_TEAM_ID          Optional Apple team ID.
  AGENT_USER_STATUS_SKIP_STAPLE=1           Skip stapling after notarization.

The script never installs the package and never reads signing secrets unless
one of the signing/notarization variables is set.
EOF
}

log() {
  printf '[macos-pkg] %s\n' "$*"
}

fail() {
  printf '[macos-pkg] error: %s\n' "$*" >&2
  exit 1
}

quote_cmd() {
  local arg
  for arg in "$@"; do
    printf '%q ' "$arg"
  done
  printf '\n'
}

require_tool() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required tool: $1"
}

optional_lint() {
  if command -v plutil >/dev/null 2>&1; then
    plutil -lint "${ROOT}/packaging/macos/Info.plist" >/dev/null
    plutil -lint "${ROOT}/packaging/macos/entitlements.plist" >/dev/null
  else
    log "warning: plutil not found; Python metadata validation will still parse plists"
  fi

  if command -v xmllint >/dev/null 2>&1; then
    xmllint --noout "${ROOT}/packaging/macos/pkg/Distribution.xml"
  else
    log "warning: xmllint not found; Python metadata validation will still parse XML"
  fi
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

absolute_path() {
  python3 - "$1" <<'PY'
import sys
from pathlib import Path

print(Path(sys.argv[1]).expanduser().resolve())
PY
}

validate_safe_path() {
  local path="$1"
  local home_local
  home_local="$(absolute_path "${HOME}/.local")"

  [[ "$path" != "/" ]] || fail "refusing to use / as a package payload root"
  [[ "$path" != "$HOME" ]] || fail "refusing to use the home directory as a package payload root"
  [[ "$path" != "$home_local" ]] || fail "refusing to package the live ~/.local install directly"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --build)
      MODE="build"
      shift
      ;;
    --payload-root)
      PAYLOAD_ROOT="${2:?missing value for --payload-root}"
      shift 2
      ;;
    --work-dir)
      WORK_DIR="${2:?missing value for --work-dir}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:?missing value for --output}"
      shift 2
      ;;
    --version)
      VERSION="${2:?missing value for --version}"
      shift 2
      ;;
    --keep-work)
      KEEP_WORK=1
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

export LC_ALL=C
umask 022

require_tool python3
optional_lint

METADATA_VERSION="$(metadata_value validate)"
if [[ -z "$VERSION" ]]; then
  VERSION="$METADATA_VERSION"
fi

[[ "$PACKAGE_ID" =~ ^[A-Za-z0-9][A-Za-z0-9.-]+$ ]] || fail "invalid package identifier: $PACKAGE_ID"
[[ "$APP_ID" =~ ^[A-Za-z0-9][A-Za-z0-9.-]+$ ]] || fail "invalid app identifier: $APP_ID"
[[ "$VERSION" =~ ^[0-9]+(\.[0-9]+){0,3}([-+][A-Za-z0-9_.-]+)?$ ]] || fail "invalid package version: $VERSION"

PAYLOAD_ROOT="$(absolute_path "$PAYLOAD_ROOT")"
WORK_DIR="$(absolute_path "$WORK_DIR")"
if [[ -z "$OUTPUT" ]]; then
  OUTPUT="${WORK_DIR}/AgentUserStatus-${VERSION}.pkg"
fi
OUTPUT="$(absolute_path "$OUTPUT")"

validate_safe_path "$PAYLOAD_ROOT"

DISTRIBUTION="${ROOT}/packaging/macos/pkg/Distribution.xml"
RESOURCES="${ROOT}/packaging/macos/pkg/resources"
COMPONENT_PKG="${WORK_DIR}/agent-user-status.pkg"

PKGBUILD_CMD=(
  pkgbuild
  --identifier "$PACKAGE_ID"
  --version "$VERSION"
  --root "$PAYLOAD_ROOT"
)

if [[ -n "${AGENT_USER_STATUS_PKG_SIGN_IDENTITY:-}" ]]; then
  PKGBUILD_CMD+=(--sign "$AGENT_USER_STATUS_PKG_SIGN_IDENTITY")
fi
PKGBUILD_CMD+=("$COMPONENT_PKG")

PRODUCTBUILD_CMD=(
  productbuild
  --distribution "$DISTRIBUTION"
  --resources "$RESOURCES"
  --package-path "$WORK_DIR"
)

if [[ -n "${AGENT_USER_STATUS_PRODUCT_SIGN_IDENTITY:-}" ]]; then
  PRODUCTBUILD_CMD+=(--sign "$AGENT_USER_STATUS_PRODUCT_SIGN_IDENTITY")
fi
PRODUCTBUILD_CMD+=("$OUTPUT")

NOTARY_CMD=()
if [[ -n "${AGENT_USER_STATUS_NOTARY_PROFILE:-}" ]]; then
  NOTARY_CMD=(xcrun notarytool submit "$OUTPUT" --keychain-profile "$AGENT_USER_STATUS_NOTARY_PROFILE" --wait)
elif [[ -n "${AGENT_USER_STATUS_NOTARY_APPLE_ID:-}" || -n "${AGENT_USER_STATUS_NOTARY_PASSWORD:-}" || -n "${AGENT_USER_STATUS_NOTARY_TEAM_ID:-}" ]]; then
  [[ -n "${AGENT_USER_STATUS_NOTARY_APPLE_ID:-}" ]] || fail "AGENT_USER_STATUS_NOTARY_APPLE_ID is required for Apple ID notarization"
  [[ -n "${AGENT_USER_STATUS_NOTARY_PASSWORD:-}" ]] || fail "AGENT_USER_STATUS_NOTARY_PASSWORD is required for Apple ID notarization"
  [[ -n "${AGENT_USER_STATUS_NOTARY_TEAM_ID:-}" ]] || fail "AGENT_USER_STATUS_NOTARY_TEAM_ID is required for Apple ID notarization"
  NOTARY_CMD=(
    xcrun notarytool submit "$OUTPUT"
    --apple-id "$AGENT_USER_STATUS_NOTARY_APPLE_ID"
    --password "$AGENT_USER_STATUS_NOTARY_PASSWORD"
    --team-id "$AGENT_USER_STATUS_NOTARY_TEAM_ID"
    --wait
  )
fi

log "metadata ok: ${PACKAGE_NAME} ${VERSION}"
log "payload root: ${PAYLOAD_ROOT}"
log "work dir: ${WORK_DIR}"
log "output: ${OUTPUT}"

if [[ "$MODE" == "dry-run" ]]; then
  log "dry run only; no files will be created"
  log "component command:"
  quote_cmd "${PKGBUILD_CMD[@]}"
  log "product command:"
  quote_cmd "${PRODUCTBUILD_CMD[@]}"
  if [[ ${#NOTARY_CMD[@]} -gt 0 ]]; then
    log "notarization command:"
    quote_cmd "${NOTARY_CMD[@]}"
    if [[ "${AGENT_USER_STATUS_SKIP_STAPLE:-0}" != "1" ]]; then
      log "staple command:"
      quote_cmd xcrun stapler staple "$OUTPUT"
    fi
  fi
  exit 0
fi

[[ "$MODE" == "build" ]] || fail "invalid mode: $MODE"
require_tool pkgbuild
require_tool productbuild
[[ -d "$PAYLOAD_ROOT" ]] || fail "payload root does not exist: $PAYLOAD_ROOT"
[[ -d "$RESOURCES" ]] || fail "resources directory does not exist: $RESOURCES"

mkdir -p "$WORK_DIR" "$(dirname "$OUTPUT")"
rm -f "$COMPONENT_PKG" "$OUTPUT"

log "building component package"
"${PKGBUILD_CMD[@]}"

log "building product archive"
"${PRODUCTBUILD_CMD[@]}"

if [[ ${#NOTARY_CMD[@]} -gt 0 ]]; then
  require_tool xcrun
  log "submitting for notarization"
  "${NOTARY_CMD[@]}"
  if [[ "${AGENT_USER_STATUS_SKIP_STAPLE:-0}" != "1" ]]; then
    log "stapling notarization ticket"
    xcrun stapler staple "$OUTPUT"
  fi
fi

if [[ "$KEEP_WORK" != "1" ]]; then
  rm -f "$COMPONENT_PKG"
fi

log "done: $OUTPUT"
