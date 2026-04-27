# Overall Audit

Date: 2026-04-27

## Current State

- Branch: `user-status-next-dag-hardening`
- Worktree: clean at audit start
- Local delta from origin: 0 commits
- Functional requirements matrix: current

## Validation Passed

- `PYTHONPATH=src python3 -m pytest tests/unit -q`
  - 113 passed
- `python3 -m ruff check src tests scripts/update-fr-matrix.py`
- `pyright`
- `scripts/validate-docs.sh all`
- `PYTHONPATH=src python3 scripts/update-fr-matrix.py --check`
- `PYTHONPATH=src python3 -m compileall -q src/agent_user_status src/mcp tests scripts/update-fr-matrix.py`
- `./scripts/check-native-macos.sh`
- `AGENT_USER_STATUS_START_SERVICES=0 PYTHONPATH=src python3 -m agent_user_status.bootstrap install --no-start`
  - bootstrap doctor passed
- `packaging/scripts/validate-packaging.sh all`
- `packaging/scripts/validate-python-dist.sh --dry-run`
- `packaging/scripts/build-macos-pkg.sh --dry-run`

## Remaining Work

### P1: Finish the 300-line modularity sweep

Only one source file remains at or above the 300-line threshold:

- `src/agent_user_status/agent_imessage_core.py` - 302 lines

Likely next seam: split recipient/config parsing, subprocess wrappers, or message helpers into a focused support module while preserving import compatibility for current callers.

### Resolved: Duplicated worklog surfaces

`docs/worklogs/` is the canonical durable worklog surface. The duplicate root `worklogs/` tree was merged and removed.

### Resolved: macOS packaging shell contract tests

`tests/unit/test_packaging_macos.py` covers dry-run staging, unsafe payload root rejection, dry-run package command output, and malformed staged payload rejection.

### P3: Optional narrow hardening

- Review benign `pass` handlers in statusd/webcam runtime for whether comments or helper extraction would clarify intentional best-effort behavior.

### Resolved: statusd command builder edge-case tests

`tests/unit/test_statusd_commands.py` covers `eta_minutes`, `note`, bounded score/weight/max-age validation, and missing route keys for `/signal` and `/action` command builders.

## Not Currently Blocking

- Unit, lint, type, docs, native compile, bootstrap, and packaging checks are green.
- No source file exceeds the 350-line target.
- No file exceeds the 500-line hard limit.
- The remaining `TODO` scan did not find unresolved `TODO`, `FIXME`, `XXX`, `HACK`, or `NotImplemented` implementation markers.
