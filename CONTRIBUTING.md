# Contributing

This repo controls a local user-status runtime, native monitor, iMessage bridge,
and privacy-sensitive attention telemetry. Treat every change as local operator
infrastructure unless proven otherwise.

## Workflow

1. Work on a branch and open a pull request.
2. Keep runtime changes scoped to the affected collector, backend, CLI, or monitor
   surface.
3. Update docs when changing install behavior, launchd behavior, API payloads,
   privacy contracts, or GitHub automation.
4. Call out privacy impact in the pull request.

## Validation

Run the relevant local checks before asking for review:

```bash
PYTHONPATH=src python -m pytest tests/unit -q
./scripts/doctor.sh
./tests/smoke/smoke.sh
```

`doctor` and the native monitor checks are macOS-focused. CI runs the unit suite
and a Linux backend smoke path that installs without launch services, starts
`agent-user-statusd`, and exercises the HTTP contract.

## Privacy Checklist

Do not add storage or transport for:
- raw camera frames
- screenshots
- face or eye images
- facial landmarks
- biometric embeddings
- raw gaze streams
- typed text, key names, or transcripts
- audio waveforms or transcripts

Allowed runtime signals should stay derived, bounded, and short-lived.
