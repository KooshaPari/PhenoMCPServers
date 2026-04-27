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

### P2: Add pytest coverage for macOS packaging shell contracts

Packaging shell validation passes, but there is no direct pytest coverage for the dry-run and safety behavior of:

- `packaging/scripts/stage-macos-payload.sh`
- `packaging/scripts/build-macos-pkg.sh`
- `packaging/scripts/macos-pkg-lib.sh`

Recommended tests:

- dry-run staging accepts a fake app/bin source under repo `build/`
- dry-run staging rejects unsafe payload roots
- dry-run package build prints staging, `pkgbuild`, and `productbuild` commands
- malformed staged payload fails validation

### Resolved: Duplicated worklog surfaces

`docs/worklogs/` is the canonical durable worklog surface. The duplicate root `worklogs/` tree was merged and removed.

### P3: Optional narrow hardening

- Add direct unit tests for `statusd_commands.py` edge cases: `eta_minutes`, `note`, clamped score/weight/max-age, and missing required keys.
- Review benign `pass` handlers in statusd/webcam runtime for whether comments or helper extraction would clarify intentional best-effort behavior.

## Not Currently Blocking

- Unit, lint, type, docs, native compile, bootstrap, and packaging checks are green.
- No source file exceeds the 350-line target.
- No file exceeds the 500-line hard limit.
- The remaining `TODO` scan did not find unresolved `TODO`, `FIXME`, `XXX`, `HACK`, or `NotImplemented` implementation markers.
