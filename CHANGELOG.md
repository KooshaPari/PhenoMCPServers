# Changelog

All notable changes to this project will be documented in this file.

## 📚 Documentation
- Docs(worklog): initialize first-entry bootstrap (`6652f57`)
- Docs(wave-4): scaffold FUNCTIONAL_REQUIREMENTS.md with 6 stubs (`b3d0c66`)
- Docs(fr): scaffold FUNCTIONAL_REQUIREMENTS.md with 8 FR stubs (`089dd58`)
## 🔨 Other
- Chore(governance): adopt CLAUDE.md + governance framework

Enable AgilePlus spec tracking, FR traceability, and standard project conventions. Wave-5 governance push.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com> (`63ecf7e`)
- Chore(ci): adopt phenotype-tooling quality-gate + fr-coverage (`e1e919d`)
- Add derived head pose telemetry

Document OptiKey and head-tracking research, publish bounded head pose and framing telemetry from the webcam tracker, and surface those signals in the native monitor without accepting raw frame or landmark payloads.\n\nCo-authored-by: Codex <noreply@openai.com> (`a0a1bf5`)
- Harden webcam calibration recovery

Add derived-only webcam acquisition diagnostics, lower the MediaPipe acquisition thresholds for the MacBook camera, split the live tracker loop out of the CLI, and make the native monitor calibration badge clickable. Explicit alignment events can now seed passive correction even when the current calibration marks gaze unreliable, while stale explicit alignment remains rejected.\n\nCo-authored-by: Codex <noreply@openai.com> (`9e66203`)
- Complete user status runtime hardening

Add session MCP surfaces, native session monitor support, privacy-safe state retention, package validation, and eye-tracker liveness fixes.

Co-authored-by: Codex <noreply@openai.com> (`68b6379`)
- Install quality gate type imports

Install pytest and numpy in the quality-gates job so Pyright can resolve test and calibration imports in CI.

Validation: PYTHONPATH=src python3 -m ruff check .; pyright; PYTHONPATH=src python3 -m pytest tests/unit -q

Co-authored-by: Codex <noreply@openai.com> (`6d5c620`)
- Close session packaging and quality gaps

Add macOS package build automation, repeated/stuck gaze evaluation detection, session event ring and stop-hook session publishing, and enforce Ruff/Pyright plus package metadata checks in CI.

Validation: PYTHONPATH=src python3 -m pytest tests/unit -q; PYTHONPATH=src python3 -m ruff check .; pyright; packaging/scripts/build-macos-pkg.sh --dry-run; ./scripts/doctor.sh; ./tests/smoke/smoke.sh

Co-authored-by: Codex <noreply@openai.com> (`b9b5287`)
- Recognize app-bundle monitor in session scan

Keep the privacy-safe session scan aware of the installed app-bundle executable name while preserving raw-argv and cwd redaction defaults.

Validation: PYTHONPATH=src python3 -m pytest tests/unit -q; ./scripts/doctor.sh

Co-authored-by: Codex <noreply@openai.com> (`12711bf`)
- Install native app bundle and session scan

Build the macOS tray as an app bundle for the local installer, move native bootstrap logic out of the CLI, add native calibration eval counters, and expose privacy-safe agent session scanning.

Validation: PYTHONPATH=src python3 -m pytest tests/unit -q; ./scripts/doctor.sh; ./tests/smoke/smoke.sh

Co-authored-by: Codex <noreply@openai.com> (`b5f26fc`)
- Extend packaging sessions and scoped messaging

Add platform packaging metadata, scoped sponsor recipient support, privacy-safe session registry surfaces, and gaze evaluation counters.

Co-authored-by: Codex <noreply@openai.com> (`da805e1`)
- Harden messaging and packaging roadmap

Centralize runtime binary lookup, tighten scoped messaging defaults, and extend the DAG for native app packaging and session-bus work.

Co-authored-by: Codex <noreply@openai.com> (`fa289bb`)
- Harden repo governance setup

Add repo governance docs, backend smoke CI, installed runtime fixes, native gaze evaluation diagnostics, and post-bootstrap session DAG updates.

Co-authored-by: Codex <noreply@openai.com> (`331260d`)
- Add GitHub automation scaffolding

Include CI, issue templates, PR template, and session docs updates.

Co-authored-by: Codex <noreply@openai.com> (`a95a7de`)
- Initial agent-user-status setup

Add the current runtime, docs scaffold, and validation artifacts.

Co-authored-by: Codex <noreply@openai.com> (`b262ab7`)