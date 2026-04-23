#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${AGENT_USER_STATUS_PYTHON_BIN:-python3}"

exec env \
  AGENT_USER_STATUS_SOURCE_ROOT="${ROOT}" \
  PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" \
  "${PYTHON_BIN}" -m agent_user_status.bootstrap doctor "$@"
