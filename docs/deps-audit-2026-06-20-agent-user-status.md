# Dependency Audit — agent-user-status

**Date:** 2026-06-20
**Scope:** Python (uv via pyproject.toml), macOS native Swift components, CI/CD
**Auditor:** forge agent W11-3-08

---

## Dependency Tree Summary

| Category | Count |
|---|---|
| Direct runtime deps | 0 (all optional via `[eye]` extra) |
| Optional `[eye]` deps | 4 (mediapipe, numpy, opencv-python, pyobjc-framework-cocoa) |
| Transitive deps resolved | 22 packages total in uv.lock |
| Swift native files | 12 standalone .swift files (no Package.swift — macOS system frameworks) |
| Dev tools | pytest, ruff, pyright |

Command: `uv tree` (Python dependency tree for the project).

---

## Duplicate Dependencies

### 1. `opencv-python` vs `opencv-contrib-python`

| Package | Version | Source |
|---|---|---|
| `opencv-python` | `4.13.0.92` | Explicit `[eye]` optional dep in pyproject.toml |
| `opencv-contrib-python` | `4.13.0.92` | Transitive dep from `mediapipe>=0.10.33` |

**Issue:** Both are installed at the same version. `opencv-contrib-python` is a superset of `opencv-python` (includes the contrib modules). The project only uses `import cv2` (`webcam_support.py:61`), which works with either package. Having both wastes ~100 MB disk space and creates ambiguity about which is actually required.

**Severity:** Low (wasted disk, no runtime conflict)

**Fix:** Replace `opencv-python>=4.10` with `opencv-contrib-python>=4.10` in pyproject.toml, and update error messages in `webcam_support.py` and `bootstrap_cli.py` to reference `opencv-contrib-python`.

---

## Outdated Deps / Version Drift

### 2. Python 3.11 references in code

| File | Line | Current text | Should be |
|---|---|---|---|
| `src/agent_user_status/webcam_support.py` | 63 | `python3.11 -m pip install opencv-python` | `python3 -m pip install opencv-contrib-python` |
| `src/agent_user_status/webcam_support.py` | 71 | `python3.11 -m pip install numpy` | `python3 -m pip install numpy` |
| `src/agent_user_status/webcam_support.py` | 79 | `python3.11 -m pip install mediapipe` | `python3 -m pip install mediapipe` |
| `src/agent_user_status/bootstrap_cli.py` | 389 | `shutil.which("python3.11")` | Should prefer python3.12+ |

**Issue:** The project declares `requires-python = ">=3.12"` in pyproject.toml, but error messages and fallback paths still reference `python3.11`. In mid-2026, Python 3.11 is EOL.

**Severity:** Medium (misleading error messages, wrong fallback)

**Fix:** Update to `python3.12` or use generic `python3`.

### 3. CI dev-dependency version drift

The CI workflow (`ci.yml`) installs tools via raw pip:

```
python -m pip install --upgrade pip ruff pyright pytest numpy
```

This bypasses the `uv.lock` file, meaning CI may run with different versions than local development. The `quality-gates` job installs `numpy` as a dev dependency but it's only needed by `[eye]` extra code paths.

**Severity:** Low (no current breakage, but drift risk)

**Fix:** Use `uv sync --only-dev` or `uv run --with` for CI tooling.

---

## DRY Opportunities

### 4. Shell script boilerplate duplication

**Files:** `scripts/doctor.sh`, `scripts/install.sh`, `scripts/uninstall.sh`, `scripts/setup-eye-tracker.sh`

These 4 scripts are ~90% identical — same shebang, same `set -euo pipefail`, same `ROOT`/`PYTHON_BIN` resolution, same `env` forwarding of `AGENT_USER_STATUS_SOURCE_ROOT` and `PYTHONPATH`. The only difference is the subcommand name passed to `bootstrap`:

| Script | Subcommand |
|---|---|
| `doctor.sh` | `doctor` |
| `install.sh` | `install` |
| `uninstall.sh` | `uninstall` |
| `setup-eye-tracker.sh` | `setup-eye-tracker` |

**Severity:** Medium (maintenance burden — adding a new subcommand requires copying the boilerplate again)

**Fix:** Consolidate into a single dispatcher script at `scripts/run.sh` that accepts the subcommand as `$1`. Example:

```bash
#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${AGENT_USER_STATUS_PYTHON_BIN:-python3}"
exec env \
  AGENT_USER_STATUS_SOURCE_ROOT="${ROOT}" \
  PYTHONPATH="${ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" \
  "${PYTHON_BIN}" -m agent_user_status.bootstrap "$@"
```

Then symlink or inline: `scripts/doctor.sh` → `run.sh doctor`, etc.

### 5. CI `actions/checkout` duplication

The workflow `ci.yml` repeats the same `actions/checkout@<sha>` step across all 4 jobs (`quality-gates`, `package-metadata`, `unit-tests`, `backend-smoke`). Each has the identical pin.

**Severity:** Low (standard practice, but a reusable workflow or composite action could reduce duplication)

### 6. Error-handling uniformity

The `webcam_support.py` module has three nearly identical try/except blocks for optional dependencies (`import_cv2`, `import_numpy`, `import_mediapipe`). These could be unified:

```python
def _import_optional(name: str, display: str, pip_pkg: str) -> Any:
    try:
        return __import__(name)
    except ImportError as exc:
        raise TrackerError(
            f"{display} is required. Install with: pip install {pip_pkg}"
        ) from exc
```

**Severity:** Low (cosmetic, but the pattern is repeated 3x)

---

## Summary of Action Items

| # | Category | Item | Severity | Fix planned |
|---|---|---|---|---|
| 1 | Duplicate dep | `opencv-python` + `opencv-contrib-python` | Low | **Yes** — replace dep in pyproject.toml |
| 2 | Version drift | Python 3.11 references in error messages | Medium | **Yes** — update to 3.12/generic |
| 3 | Version drift | CI bypasses uv.lock | Low | Documentation only |
| 4 | DRY | 4 nearly identical shell scripts | Medium | Documentation only |
| 5 | DRY | CI checkout step duplication | Low | Documentation only |
| 6 | DRY | Error-handling pattern repetition | Low | Documentation only |

---

## Files Examined

- `pyproject.toml` — project metadata, optional deps
- `uv.lock` — full resolved dependency tree
- `src/agent_user_status/*.py` — Python source for dep usage
- `scripts/*.sh` — shell bootstrap scripts
- `.github/workflows/*.yml` — CI pipeline definitions
- `src/native/macos/*.swift` — Swift native components
- `launchd/*.plist` — launchd service definitions
- `packaging/*` — macOS packaging scripts
- `Taskfile.yml`, `justfile`, `lefthook.yml` — task runner configs
