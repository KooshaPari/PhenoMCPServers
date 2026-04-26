# Known Issues

- Ruff and Pyright are now enforced in CI.
- `doctor` remains a local/macOS validation gate because it checks Swift/AppKit,
  LaunchAgent layout, and the live local backend.
- Current webcam gaze calibration can still be poor even when the evaluator is
  functioning correctly. Treat mean/P95 error above a few hundred pixels as
  calibration/model failure or intentional look-away, not as an acceptable
  smoothing artifact.
- Webcam tracker publishing now treats backend socket resets as transient
  publish failures instead of terminating the tracker loop.
- Missing-presence tracker updates use the derived state `presence_missing` so
  the backend can stay fresh without accepting raw face/biometric wording.
- `probe-camera` now runs an aggregate derived-presence diagnostic over multiple
  frames. On this MacBook camera, relaxed MediaPipe thresholds
  (`0.2/0.2/0.2`) produced 45/45 derived samples, but confidence stayed low
  because the detected head/eye region was small in frame. Runtime defaults now
  use those lower acquisition thresholds and a `0.1` sample-confidence floor.
- Native and CLI evaluation both report per-target accepted/rejected sample
  counts, rejection reasons, and repeated/stuck sample detection.
- Runtime executable lookup is centralized for Python/MCP wrappers and the
  native calibration/evaluation controls now read bootstrap-generated
  `runtime_paths.json` metadata with environment overrides.
- The macOS tray now builds into `Agent User Status.app`, and the pkg helper can
  dry-run/build staged product archives. Package signing, notarization, icon
  assets, and `/Applications`/Homebrew cask installation are still pending.
- Session heartbeats/events now have privacy-safe JSONL, HTTP, CLI, MCP, and
  native monitor surfaces. Passive process/tmux scanning is available through
  `agent-imessage session-scan`; child-agent lifecycle can be recorded through
  `session-child-spawn` and `session-child-close`.
- The live checkout passes unit tests, Ruff, Pyright, Swift compile, packaging
  metadata validation, Python dist build validation, backend smoke, and the
  local `doctor` gate, including installed runtime layout and CLI import checks.

These do not affect the validated local runtime.
