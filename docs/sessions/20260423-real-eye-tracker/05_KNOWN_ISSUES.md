# Known Issues

- Ruff and Pyright are now enforced in CI.
- `doctor` remains a local/macOS validation gate because it checks Swift/AppKit,
  LaunchAgent layout, and the live local backend.
- Current webcam gaze calibration can still be poor even when the evaluator is
  functioning correctly. Treat mean/P95 error above a few hundred pixels as
  calibration/model failure or intentional look-away, not as an acceptable
  smoothing artifact.
- Native and CLI evaluation both report per-target accepted/rejected sample
  counts, rejection reasons, and repeated/stuck sample detection.
- Runtime executable lookup is centralized for Python/MCP wrappers. The native
  calibration/evaluation controls still use the installed eye-tracker venv path
  and should gain an override-aware source of truth before non-default native
  install prefixes become common.
- The macOS tray now builds into `Agent User Status.app`, and the pkg helper can
  dry-run/build staged product archives. Package signing, notarization, icon
  assets, and `/Applications`/Homebrew cask installation are still pending.
- Session heartbeats/events now have a privacy-safe JSONL store and HTTP/CLI
  surfaces. Passive process/tmux session scanning is available through
  `agent-imessage session-scan`. Stop-hook event publishing is done; automatic
  subagent spawn/close events still require wrapper integration.

These do not affect the validated local runtime.
