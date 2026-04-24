# Testing Strategy

Validation performed before the GitHub bootstrap:
- `./scripts/doctor.sh`
- `./tests/smoke/smoke.sh`
- `PYTHONPATH=src python -m pytest tests/unit -q`

For the setup pass itself, the only required checks are:
- repo/remote wiring
- clean commit state
- successful push to GitHub
- GitHub Actions unit-test workflow
- GitHub Actions backend smoke workflow
