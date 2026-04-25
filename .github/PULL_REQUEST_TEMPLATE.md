# Summary

Describe the user-facing change and the runtime surface it affects.

# Runtime Surface

- [ ] Backend / HTTP API
- [ ] CLI / scripts / install behavior
- [ ] Native monitor / tray / overlay
- [ ] Eye, input, audio, process, prompt, or window telemetry
- [ ] GitHub automation / docs only

# Privacy Impact

- Data tier touched: `none` / `tier-1-derived` / `tier-2-aggregate`
- New persisted fields: `none` or list exact fields and retention window
- New transport or endpoint: `none` or list exact route/command
- Kill switch or consent impact: `none` or describe

Confirm each boundary:

- [ ] No raw camera frames, screenshots, face/eye images, landmarks,
      embeddings, or raw gaze streams.
- [ ] No typed text, key names, prompt transcripts, audio samples, or audio transcripts.
- [ ] Backend remains loopback-only, or this PR includes a threat model and auth layer.
- [ ] Any new telemetry is derived, bounded, short-lived, and documented in
      `docs/security/PRIVACY.md`.

# Validation

- [ ] `./scripts/doctor.sh`
- [ ] `./tests/smoke/smoke.sh`
- [ ] `PYTHONPATH=src python -m pytest tests/unit -q`

# Reviewer Notes

Call out packaging, launchd, native permission, or branch-protection impacts.
