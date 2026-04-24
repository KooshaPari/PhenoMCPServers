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
- Runtime executable lookup still has hard-coded default paths in several
  modules. Centralize path resolution before expanding install prefixes.
- Branch protection should require backend smoke after PR #1 is green and merged.

These do not affect the validated local runtime.
