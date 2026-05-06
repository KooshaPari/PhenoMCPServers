# Testing Strategy

## Targeted Checks

- `git diff --check`
- `rg "sladge|AI Slop" README.md`
- `PYTHONPATH=src python -m pytest tests/unit -q`
- `./scripts/doctor.sh`
- `./tests/smoke/smoke.sh`

## Result Notes

Unit tests reached 64 passing tests before 11 loopback-bound privacy tests
failed to bind `127.0.0.1`. Doctor and smoke checks were attempted; doctor is
blocked by local disk exhaustion in the Swift module cache plus backend
loopback health denial, and smoke cannot connect to `127.0.0.1:8765`. These
blockers are carried into the projects-landing ledger instead of treated as
badge-regression signals.
