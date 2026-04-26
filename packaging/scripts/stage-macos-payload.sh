#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PAYLOAD_ROOT="${ROOT}/build/pkg/macos/payload"
APP_SOURCE="${HOME}/.local/share/agent-imessage/Agent User Status.app"
BIN_SOURCE="${HOME}/.local/bin"
MODE="dry-run"

usage() {
  cat <<'EOF'
Usage:
  packaging/scripts/stage-macos-payload.sh [options]

Options:
  --dry-run              Print staging actions without writing files. Default.
  --stage                Copy current install artifacts into the staged payload root.
  --payload-root PATH    Staged package root. Default: build/pkg/macos/payload
  --app-source PATH      Source .app bundle. Default: ~/.local/share/agent-imessage/Agent User Status.app
  --bin-source PATH      Source bin directory. Default: ~/.local/bin
  -h, --help             Show this help.

The helper copies from the current local install into a disposable package
payload. It never copies live state/log/venv support directories, installs
files, starts LaunchAgents, or modifies ~/.local.
EOF
}

log() {
  printf '[macos-stage] %s\n' "$*"
}

fail() {
  printf '[macos-stage] error: %s\n' "$*" >&2
  exit 1
}

quote_cmd() {
  local arg
  for arg in "$@"; do
    printf '%q ' "$arg"
  done
  printf '\n'
}

absolute_path() {
  python3 - "$1" <<'PY'
import sys
from pathlib import Path

print(Path(sys.argv[1]).expanduser().resolve())
PY
}

safe_payload_root() {
  local path="$1"
  local home_local
  home_local="$(absolute_path "${HOME}/.local")"

  [[ "$path" != "/" ]] || fail "refusing to stage into /"
  [[ "$path" != "$HOME" ]] || fail "refusing to stage into the home directory"
  [[ "$path" != "$home_local" ]] || fail "refusing to stage into the live ~/.local install"
  [[ "$path" == "${ROOT}/build/"* || "$path" == "${ROOT}/build" ]] || \
    fail "payload root must stay under ${ROOT}/build"
}

copy_item() {
  local source="$1"
  local target="$2"
  if [[ "$MODE" == "dry-run" ]]; then
    quote_cmd mkdir -p "$(dirname "$target")"
    quote_cmd rm -rf "$target"
    quote_cmd cp -R "$source" "$target"
    return
  fi

  mkdir -p "$(dirname "$target")"
  rm -rf "$target"
  cp -R "$source" "$target"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --stage)
      MODE="stage"
      shift
      ;;
    --payload-root)
      PAYLOAD_ROOT="${2:?missing value for --payload-root}"
      shift 2
      ;;
    --app-source)
      APP_SOURCE="${2:?missing value for --app-source}"
      shift 2
      ;;
    --bin-source)
      BIN_SOURCE="${2:?missing value for --bin-source}"
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

PAYLOAD_ROOT="$(absolute_path "$PAYLOAD_ROOT")"
APP_SOURCE="$(absolute_path "$APP_SOURCE")"
BIN_SOURCE="$(absolute_path "$BIN_SOURCE")"

safe_payload_root "$PAYLOAD_ROOT"

[[ -d "$APP_SOURCE" ]] || fail "missing .app source: $APP_SOURCE"
[[ -f "$APP_SOURCE/Contents/Info.plist" ]] || fail "missing app Info.plist: $APP_SOURCE"
[[ -d "$BIN_SOURCE" ]] || fail "missing bin source: $BIN_SOURCE"

BINARIES=(
  agent-user-status
  agent-imessage
  agent-user-statusd
)

for binary in "${BINARIES[@]}"; do
  [[ -x "$BIN_SOURCE/$binary" ]] || fail "missing executable: $BIN_SOURCE/$binary"
done
[[ -d "$BIN_SOURCE/agent_user_status" ]] || fail "missing Python support modules: $BIN_SOURCE/agent_user_status"

log "mode: $MODE"
log "payload root: $PAYLOAD_ROOT"
log "app source: $APP_SOURCE"
log "bin source: $BIN_SOURCE"

if [[ "$MODE" == "stage" ]]; then
  rm -rf "$PAYLOAD_ROOT"
  mkdir -p "$PAYLOAD_ROOT"
else
  quote_cmd rm -rf "$PAYLOAD_ROOT"
fi

copy_item "$APP_SOURCE" "$PAYLOAD_ROOT/Applications/Agent User Status.app"

for binary in "${BINARIES[@]}"; do
  copy_item "$BIN_SOURCE/$binary" "$PAYLOAD_ROOT/usr/local/bin/$binary"
done
copy_item "$BIN_SOURCE/agent_user_status" "$PAYLOAD_ROOT/usr/local/bin/agent_user_status"

if [[ "$MODE" == "stage" ]]; then
  find "$PAYLOAD_ROOT" -type d -exec chmod 0755 {} +
  find "$PAYLOAD_ROOT/usr/local/bin" -type f -exec chmod 0755 {} +
fi

log "done"
