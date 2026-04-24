# Security Policy

## Reporting

Report vulnerabilities privately to the repository owner. Do not open public
issues for bugs that could expose local telemetry, private messages, camera
access, keyboard state, process context, or authentication material.

## Data Boundary

This project accepts only derived local presence signals. Raw camera frames,
screenshots, biometric data, raw gaze streams, typed text, key names, and audio
transcripts are out of scope and should be rejected by the backend.

## Supported Surface

The current supported runtime is local macOS with loopback-only backend access.
Non-loopback transport requires a threat model and authentication layer before it
is enabled.
