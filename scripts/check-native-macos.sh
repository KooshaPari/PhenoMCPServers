#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${TMPDIR:-/tmp}/agent-user-status-native-monitor-check"

swiftc \
  "${ROOT}"/src/native/macos/*.swift \
  -o "${OUT}" \
  -framework AppKit \
  -framework CoreGraphics

test -x "${OUT}"
echo "native macOS monitor compile ok: ${OUT}"
