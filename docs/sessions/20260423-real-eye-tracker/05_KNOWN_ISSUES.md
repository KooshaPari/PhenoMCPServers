# Known Issues

- Ruff is configured but not yet enforced because the current tree has existing
  style findings.
- `doctor` remains a local/macOS validation gate because it checks Swift/AppKit,
  LaunchAgent layout, and the live local backend.

These do not affect the validated local runtime.
