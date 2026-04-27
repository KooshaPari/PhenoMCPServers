# Overall Audit

Date: 2026-04-27

## Current State

- Branch: `user-status-next-dag-hardening`
- Worktree: clean at latest audit refresh
- Local delta from origin: see `git status --short --branch`
- Functional requirements matrix: current

## Validation Passed

- `PYTHONPATH=src python3 -m pytest tests/unit -q`
  - 134 passed
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

No P1/P2 audit blockers remain from this session's original checklist.

### Resolved: 300-line modularity sweep

All tracked source, test, packaging, script, native, and workflow files are now under the 300-line threshold. The final source item was resolved by extracting recipient primitives from `agent_imessage_core.py`.

### Resolved: Duplicated worklog surfaces

`docs/worklogs/` is the canonical durable worklog surface. The duplicate root `worklogs/` tree was merged and removed.

### Resolved: macOS packaging shell contract tests

`tests/unit/test_packaging_macos.py` covers dry-run staging, unsafe payload root rejection, dry-run package command output, and malformed staged payload rejection.

### Resolved: statusd command builder edge-case tests

`tests/unit/test_statusd_commands.py` covers `eta_minutes`, `note`, bounded score/weight/max-age validation, and missing route keys for `/signal` and `/action` command builders.

### Resolved: intentional best-effort handlers

Benign `pass` handlers in statusd, webcam runtime, and cursor activity tracking are now documented where they intentionally absorb disconnects or transient local backend failures.

### Resolved: stale Codex guidance snippet

The unreferenced `codex/AGENTS.user-status-snippet.md` copy of broad agent guidance was removed. The canonical repo guidance remains `AGENTS.md` and `CLAUDE.md`.

## Not Currently Blocking

- Unit, lint, type, docs, native compile, bootstrap, and packaging checks are green.
- No source file exceeds the 350-line target.
- No file exceeds the 500-line hard limit.
- The remaining `TODO` scan did not find unresolved `TODO`, `FIXME`, `XXX`, `HACK`, or `NotImplemented` implementation markers.
