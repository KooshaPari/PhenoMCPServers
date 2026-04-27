# Claude Guide - agent-user-status

## Overview

`agent-user-status` is a local, privacy-first runtime that lets coding agents
estimate user availability and communicate through a structured iMessage/MCP
layer. The repo includes Python CLIs, a local HTTP status daemon, Codex hooks,
macOS LaunchAgents, a native Swift monitor, opt-in derived webcam gaze
publishing, packaging metadata, and tests.

## Stack

- Python 3.11+
- Ruff, Pyright, Pytest
- Bash packaging/bootstrap wrappers
- Swift/AppKit for the native macOS monitor
- Repo-local Codex hook config in `.codex/`

## Required Validation

Run focused tests first, then widen to the relevant gates before committing:

```bash
PYTHONPATH=src python3 -m pytest tests/unit -q
python3 -m ruff check src tests scripts/update-fr-matrix.py
pyright
scripts/validate-docs.sh all
PYTHONPATH=src python3 scripts/update-fr-matrix.py --check
git diff --check
```

For runtime, native, or packaging changes, also run the matching gates:

```bash
./scripts/check-native-macos.sh
AGENT_USER_STATUS_START_SERVICES=0 PYTHONPATH=src python3 -m agent_user_status.bootstrap install --no-start
packaging/scripts/validate-packaging.sh all
packaging/scripts/validate-python-dist.sh --dry-run
packaging/scripts/build-macos-pkg.sh --dry-run
```

Smoke checks:

```bash
AGENT_USER_STATUS_SMOKE_SKIP_IMESSAGE=1 ./tests/smoke/smoke.sh
```

## Repo Contracts

- Functional requirements live in `docs/FUNCTIONAL_REQUIREMENTS.md`; the root
  `FUNCTIONAL_REQUIREMENTS.md` is only a pointer.
- Every unit test file must carry canonical `FR-AGENT_USER_STATUS-*` markers.
- Regenerate `docs/reference/fr_coverage_matrix.md` with
  `PYTHONPATH=src python3 scripts/update-fr-matrix.py --write` after changing
  requirement markers or traces.
- Durable worklogs live in `docs/worklogs/`; task execution notes belong under
  `docs/sessions/<session-id>/`.
- Keep source, test, packaging, script, native, and workflow files below the
  300-line target where practical.
- The runtime must not store or publish raw camera frames, screenshots,
  biometric data, raw gaze streams, or private message content. Only derived
  state, scores, short-lived zones, and redacted status payloads belong in local
  telemetry surfaces.

## Entry Points

- `agent-user-status` -> `agent_user_status.bootstrap:main`
- `agent-imessage` -> `agent_user_status.agent_imessage:main`
- `agent-imessage-mcp` -> `mcp.agent_imessage_mcp:main`
- `agent-user-statusd` -> `agent_user_status.statusd:main`
- `agent-user-status-cursor-tracker` -> `agent_user_status.cursor_tracker:main`
- `agent-user-status-webcam-eye-tracker` ->
  `agent_user_status.webcam_eye_tracker:main`

Shell scripts in `scripts/` are compatibility wrappers around the packaged CLI.
