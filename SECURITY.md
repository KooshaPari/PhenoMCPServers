# Security Policy

## Reporting

Report vulnerabilities through GitHub private security advisories:

https://github.com/kooshapari/agent-user-status/security/advisories/new

Do not open public issues for bugs that could expose local telemetry, private
messages, camera access, keyboard state, process context, prompt/window context,
audio state, or authentication material.

Include:

- affected command, endpoint, collector, native UI surface, or LaunchAgent;
- exact local version or commit;
- whether the issue exposes raw data or only derived state;
- reproduction steps that avoid sharing private messages, typed text, images, or
  audio content.

## Data Boundary

This project accepts only derived local presence signals. Raw camera frames,
screenshots, biometric data, raw gaze streams, typed text, key names, and audio
transcripts are out of scope and should be rejected by the backend.

Severity is highest when a bug stores, logs, transports, displays, or persists
raw sensor or message content. Treat unexpected non-loopback exposure as a
security issue even when the payload is derived.

## Supported Surface

The current supported runtime is local macOS with loopback-only backend access.
Non-loopback transport requires a threat model and authentication layer before it
is enabled.

## Triage Expectations

- Acknowledge private reports before public discussion.
- Reproduce with local synthetic data when possible.
- Prefer fixes that reject unsafe payloads at the boundary and add a smoke or unit
  regression test.
- Update `docs/security/PRIVACY.md` whenever a supported telemetry envelope,
  retention behavior, endpoint, or collector boundary changes.
