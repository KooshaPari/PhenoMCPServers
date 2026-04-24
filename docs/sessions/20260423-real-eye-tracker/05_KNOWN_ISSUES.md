# Known Issues

- Ruff is configured but not yet enforced because the current tree has existing
  style findings.
- Pyright is configured but not yet enforced because the current tree has
  existing typing findings.
- `doctor` remains a local/macOS validation gate because it checks Swift/AppKit,
  LaunchAgent layout, and the live local backend.
- Current webcam gaze calibration can still be poor even when the evaluator is
  functioning correctly. Treat mean/P95 error above a few hundred pixels as
  calibration/model failure or intentional look-away, not as an acceptable
  smoothing artifact.
- Native evaluation now normalizes backend gaze coordinates into AppKit screen
  coordinates and reports discarded stale/unreliable samples, but follow-up work
  still needs per-target rejection reasons and parity with CLI evaluation.
- Runtime executable lookup is centralized for Python/MCP wrappers. The native
  calibration/evaluation controls still use the installed eye-tracker venv path
  and should gain an override-aware source of truth before non-default native
  install prefixes become common.
- Governance templates now require explicit privacy classification, but automated
  lint/type gates are still pending until existing Ruff and Pyright findings are
  closed.

These do not affect the validated local runtime.
