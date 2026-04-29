# Agent User Status

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/KooshaPari/agent-user-status/actions/workflows/ci.yml/badge.svg)](https://github.com/KooshaPari/agent-user-status/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](pyproject.toml)
[![AI Slop Inside](https://sladge.net/badge.svg)](https://sladge.net)

Local, privacy-first user-status runtime for Codex/Claude agents.

This repo packages the current live prototype into a proper source tree. The
real CLI boundary is the `agent-user-status` bootstrap CLI plus the installable
console-script surface declared in `pyproject.toml`; the shell scripts are thin
helpers that pin the source root and hand off to that CLI:

- iMessage contact and wait helpers.
- CLI-backed MCP server for Codex/Claude.
- Persistent local status backend.
- Native macOS monitor with a floating gaze dot and pinned status panel.
- Cursor tracker for activity telemetry and click-only correction anchors.
- Opt-in MacBook webcam tracker with local calibration and derived coordinates.
- LaunchAgent templates, bootstrap/install scripts, smoke checks, and privacy docs.
- Platform packaging metadata under `packaging/` for future app-store,
  package-manager, and managed-install routes.

The design goal is not a toy presence flag. The long-term target is a local event
runtime that correlates input streams, output streams, environment state, and
agent-session context so agents know when to wait, summarize, handhold, or defer.

## Current Components

```text
pyproject.toml
  project.scripts        # installable console-script boundary
src/agent_user_status/
  agent_imessage.py       # iMessage/status CLI entrypoint
  bootstrap.py            # bootstrap CLI compatibility shim (delegates to bootstrap_cli)
  statusd.py              # local HTTP backend entrypoint
  cursor_tracker.py       # coordinate-free activity plus click correction entrypoint
  webcam_eye_tracker.py   # opt-in webcam gaze tracker entrypoint
src/mcp/
  agent_imessage_mcp.py   # stdio MCP entrypoint
src/native/macos/
  AgentUserStatusMonitor.swift
launchd/
  com.phenotype.agent-user-status*.plist
scripts/
  install.sh              # thin wrapper around the bootstrap CLI
  uninstall.sh            # thin wrapper around the bootstrap CLI
  doctor.sh               # thin wrapper around the bootstrap CLI
  setup-eye-tracker.sh    # thin wrapper around the bootstrap CLI
tests/smoke/
  smoke.sh
```

## Quick Install

```bash
./scripts/install.sh
./scripts/doctor.sh
```

The bootstrap CLI stages the console-script entrypoints into `~/.local/bin`,
copies support modules into the same prefix, installs LaunchAgents into
`~/Library/LaunchAgents`, builds the Swift monitor, and restarts launchd jobs.

## CLI & Lifecycle

The shell scripts are compatibility wrappers around the packaged CLI:

```bash
agent-user-status install --help
agent-user-status uninstall --help
agent-user-status doctor --help
agent-user-status setup-eye-tracker --help
```

Useful lifecycle flags:

- `agent-user-status install --no-start` installs files and LaunchAgents without
  starting services.
- `AGENT_USER_STATUS_STRICT=0 agent-user-status install --no-start` skips the
  post-install doctor check, which is useful in CI or packaging dry runs.
- `agent-user-status uninstall --no-remove` stops services without removing
  installed files.
- `agent-user-status uninstall --dry-run` prints planned removals.
- `agent-user-status uninstall --purge` removes state and logs as well as
  installed files.

The native monitor, LaunchAgents, camera permissions, and strict doctor checks
are macOS-focused. The Linux CI path validates the Python unit suite and starts
the loopback backend directly for HTTP smoke checks.

## Packaging Metadata

The `packaging/` directory contains side-effect-free discovery and installer
metadata scaffolds:

- `packaging/macos`: app `Info.plist`, entitlements, and `.pkg` distribution
  metadata for a future `Agent User Status.app`.
- `packaging/windows`: MSIX manifest scaffold for a future WinUI 3 or native
  Windows shell.
- `packaging/linux`: Freedesktop `.desktop` and AppStream metainfo scaffold.

The installer now builds `Agent User Status.app` under the runtime share
directory and launches the tray from the app bundle executable. The legacy
`agent-user-status-native-monitor` binary is still staged as a compatibility
entrypoint.

## Install Prefixes

Runtime executable lookup is centralized. Use these environment variables for a
non-default prefix:

- `AGENT_USER_STATUS_BIN_DIR`: installed console commands. Defaults to
  `~/.local/bin`.
- `AGENT_USER_STATUS_SHARE_DIR`: shared runtime assets and native monitor bundle.
  Defaults to `~/.local/share/agent-imessage`.
- `AGENT_IMESSAGE_STATE_DIR`: state and short-lived derived signal files.
  Defaults to `$AGENT_USER_STATUS_SHARE_DIR/state`.
- `AGENT_USER_STATUS_LAUNCHD_DIR`: LaunchAgent install location. Defaults to
  `~/Library/LaunchAgents`.
- `AGENT_USER_STATUS_EYE_VENV`: dedicated webcam tracker virtualenv. Defaults to
  `~/.local/share/agent-imessage/eye-tracker-venv`.
- `AGENT_IMESSAGE_BIN`: explicit `agent-imessage` binary used by wrappers.
  Defaults to `$AGENT_USER_STATUS_BIN_DIR/agent-imessage`.
- `IMSG_BIN`: explicit `imsg` binary used for Messages access. Defaults to
  `$AGENT_USER_STATUS_BIN_DIR/imsg`.

## Webcam Eye Tracking

The real webcam tracker is opt-in and runs separately from the status daemon.
It uses a dedicated Python 3.11 environment because MediaPipe is the limiting
dependency on macOS:

```bash
./scripts/setup-eye-tracker.sh
~/.local/share/agent-imessage/eye-tracker-venv/bin/python \
  ~/.local/bin/agent-user-status-webcam-eye-tracker calibrate
launchctl kickstart -k gui/$(id -u)/com.phenotype.agent-user-status-webcam-eye-tracker
```

The calibration command opens a 9-point screen target and uses the MacBook
webcam. Frames stay in memory; only derived gaze coordinates and confidence are
posted to `POST /dev/eye`.

Camera permission is service-specific on macOS. Grant Camera access to the exact
Python binary used by the LaunchAgent, which defaults to
`~/.local/share/agent-imessage/eye-tracker-venv/bin/python`. `launchd` will not
surface an interactive permission prompt for that job.

The native macOS tray menu includes `Toggle Popup View`, `Start Eye Tracker`,
`Stop Eye Tracker`, `Recalibrate Eye Tracker`, and `Evaluate Calibration`.
`Toggle Popup View` hides or restores the pinned panel without restarting the
service. Recalibration runs the packaged eye-tracker command in the background
from the tray controls; it does not open Terminal.
Evaluation opens a native 9-point test canvas and reports mean/P95
screen-coordinate error, projection-hold risk, and calibration quality without
storing frames.
The CLI evaluator also reports per-target accepted sample counts and rejection
reasons such as settling, low confidence, no face sample, unstable confidence,
or camera-frame unavailable.

The tracker now uses a projection-hold recovery gate instead of freezing on a
single outlier. Short outlier runs are smoothed through, while several stable
frames are required before a hold releases again. The live `/dev/state` payload
also carries calibration error and quality fields so the panel can surface
diagnostic state without raw sensor storage.

## Runtime URLs

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/privacy
curl -s http://127.0.0.1:8765/status
curl -s http://127.0.0.1:8765/dev/state
curl -s http://127.0.0.1:8765/sessions
```

Eye/cursor style derived coordinate updates:

```bash
curl -s -X POST http://127.0.0.1:8765/dev/eye \
  -H 'content-type: application/json' \
  -d '{"screen_x":720,"screen_y":450,"screen_width":1440,"screen_height":900,"score":0.9,"state":"looking_at_screen:center","max_age_seconds":3}'
```

## Privacy Boundary

Eye tracking, webcam, process, and user-presence telemetry are treated as highly
confidential. The backend accepts derived signals only: coordinates, confidence,
screen zone, scores, ETA, and short notes. It rejects raw camera frames, images,
screenshots, facial landmarks, biometric embeddings, and raw gaze streams.

The source-side learning lane also carries only derived gaze reliability metadata.
ETA learning, correction learning, and process-specific action attribution skip
unstable gaze periods and only learn from reliable samples. Reliable-only correction
feeds are exposed through `GET /correction/events?reliable_only=true`.

The monitor also derives a coarse workspace role from existing `/status` signals
so terminal-agent contexts can be labeled as plain terminal, coding terminal, or
agent terminal without adding any raw terminal content capture.

See [docs/security/PRIVACY.md](docs/security/PRIVACY.md).

## Scoped Messaging And Sessions

The messaging layer is intentionally scoped. CLI and MCP calls support only
closed recipient roles:

- `koosha`, configured by the existing `AGENT_IMESSAGE_*` keys.
- `sponsor`, configured by `AGENT_IMESSAGE_SPONSOR_PHONE_E164`,
  `AGENT_IMESSAGE_SPONSOR_EMAIL`, and `AGENT_IMESSAGE_SPONSOR_NAME`.

There is no arbitrary contact search or `--to` surface. Generic direct Messages
MCP registration is disabled unless `AGENT_IMESSAGE_ALLOW_GENERIC_MESSAGES_MCP=1`
is set for explicit local admin repair.

Agents can also publish privacy-safe session state:

```bash
agent-imessage session-heartbeat --session-id codex-123 --agent codex --cwd "$PWD"
agent-imessage session-event --session-id codex-123 --event-type validation --state pytest_passed
agent-imessage sessions --limit 20
agent-imessage session-scan
```

The backend exposes the same store through `POST /session/heartbeat`,
`POST /event`, and `GET /sessions`. Session records reject raw transcripts,
prompt text, screenshots, camera data, keystrokes, and audio-like payloads.
`session-scan` discovers likely local agent processes and tmux panes without raw
command arguments or full cwd paths by default. Use `--include-cwd` only for
explicit local debugging.

## Long-Term Architecture

The current implementation is a working local bridge. The target architecture is
larger: a typed local event bus, hot/warm encrypted state store, native collectors
per OS, and an agent policy engine.

See [docs/architecture/LONG_TERM_PLAN.md](docs/architecture/LONG_TERM_PLAN.md).

## License

MIT — see [LICENSE](./LICENSE).
