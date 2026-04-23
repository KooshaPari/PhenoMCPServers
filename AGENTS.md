# AGENTS.md - agent-user-status

This repo packages local user-status and iMessage tooling for Codex/Claude
agents.

## Scope

Applies to all files in this repo.

## Rules

- Treat eye tracking, webcam, input, window, prompt, and process telemetry as
  highly confidential local data.
- Do not store raw camera frames, screenshots, facial landmarks, biometric
  embeddings, or raw gaze streams.
- Prefer derived state: coordinates, confidence, screen zone, scores, and short
  status labels.
- Keep the backend bound to `127.0.0.1` unless a threat model and auth layer are
  added first.
- Preserve the current live install under `~/.local` unless the user explicitly
  asks to overwrite it through install scripts.
- Native UI direction:
  - macOS: Swift/AppKit or SwiftUI shell.
  - Windows: WinUI 3 / Windows App SDK, Rust integration through `windows-rs`
    or a thin UI shell over a Rust core.
  - Linux: GTK4/libadwaita via `gtk-rs` for desktop-native fit; Slint is the
    Rust-first cross-platform fallback.
- Do not treat the dev cursor tracker as real eye tracking. It is only a monitor
  validation source.

## Validation

Run before reporting completion:

```bash
./scripts/doctor.sh
./tests/smoke/smoke.sh
```
