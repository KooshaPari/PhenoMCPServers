#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MODE="dry-run"
DIST_DIR="${ROOT}/dist"

usage() {
  cat <<'EOF'
Usage:
  packaging/scripts/validate-python-dist.sh [options]

Options:
  --dry-run           Validate pyproject metadata and print the build command. Default.
  --build             Build wheel and sdist, then validate artifact metadata.
  --dist-dir PATH     Output directory. Default: dist
  -h, --help          Show this help.
EOF
}

log() {
  printf '[python-dist] %s\n' "$*"
}

fail() {
  printf '[python-dist] error: %s\n' "$*" >&2
  exit 1
}

absolute_path() {
  python3 - "$1" <<'PY'
import sys
from pathlib import Path

print(Path(sys.argv[1]).expanduser().resolve())
PY
}

validate_metadata() {
  local phase="${1:-pre}"
  python3 - "$ROOT" "$DIST_DIR" "$MODE" "$phase" <<'PY'
import email.parser
import re
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

root = Path(sys.argv[1])
dist_dir = Path(sys.argv[2])
mode = sys.argv[3]
phase = sys.argv[4]
project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
name = project["name"]
version = project["version"]
scripts = project["scripts"]

if name != "agent-user-status":
    raise SystemExit(f"unexpected project name: {name}")
if not re.fullmatch(r"\d+(?:\.\d+){0,3}(?:[-+][A-Za-z0-9_.-]+)?", version):
    raise SystemExit(f"unsupported project version: {version}")
for script in ["agent-user-status", "agent-imessage", "agent-user-statusd"]:
    if script not in scripts:
        raise SystemExit(f"missing script entry point: {script}")

if mode != "build" or phase != "post":
    print(f"{name} {version}")
    raise SystemExit(0)

wheel = dist_dir / f"agent_user_status-{version}-py3-none-any.whl"
sdist = dist_dir / f"agent_user_status-{version}.tar.gz"
if not wheel.exists():
    raise SystemExit(f"missing wheel: {wheel}")
if not sdist.exists():
    raise SystemExit(f"missing sdist: {sdist}")

with zipfile.ZipFile(wheel) as archive:
    names = archive.namelist()
    metadata_name = f"agent_user_status-{version}.dist-info/METADATA"
    wheel_name = f"agent_user_status-{version}.dist-info/WHEEL"
    entry_points_name = f"agent_user_status-{version}.dist-info/entry_points.txt"
    for required in [metadata_name, wheel_name, entry_points_name, "agent_user_status/bootstrap.py"]:
        if required not in names:
            raise SystemExit(f"wheel missing {required}")
    metadata = email.parser.Parser().parsestr(archive.read(metadata_name).decode("utf-8"))
    if metadata["Name"] != name or metadata["Version"] != version:
        raise SystemExit("wheel metadata does not match pyproject")
    entry_points = archive.read(entry_points_name).decode("utf-8")
    for script in scripts:
        if f"{script} =" not in entry_points:
            raise SystemExit(f"wheel missing entry point: {script}")

with tarfile.open(sdist) as archive:
    names = archive.getnames()
    prefix = f"agent_user_status-{version}/"
    for required in ["pyproject.toml", "src/agent_user_status/bootstrap.py"]:
        if prefix + required not in names:
            raise SystemExit(f"sdist missing {required}")
PY
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
    --dist-dir)
      DIST_DIR="${2:?missing value for --dist-dir}"
      shift 2
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

command -v python3 >/dev/null 2>&1 || fail "missing required tool: python3"
DIST_DIR="$(absolute_path "$DIST_DIR")"

validate_metadata pre

BUILD_CMD=(python3 -m build --sdist --wheel --outdir "$DIST_DIR")
log "dist dir: $DIST_DIR"
if [[ "$MODE" == "dry-run" ]]; then
  log "dry run only; no files will be created"
  printf '[python-dist] build command: '
  printf '%q ' "${BUILD_CMD[@]}"
  printf '\n'
  exit 0
fi

python3 -c 'import build' >/dev/null 2>&1 || fail "missing Python build module; install with: python3 -m pip install build"
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"
(cd "$ROOT" && "${BUILD_CMD[@]}")
validate_metadata post
log "ok"
