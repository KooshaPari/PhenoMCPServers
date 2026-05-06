# Known Issues

## Live Runtime Checks

`PYTHONPATH=src python -m pytest tests/unit -q` reports 64 passing tests and
11 errors in loopback-bound privacy tests because the sandbox denies
`127.0.0.1` socket binding.

`./scripts/doctor.sh` passes Python syntax, plist validation, and installed
runtime layout checks, but Swift compile is blocked by local disk exhaustion
while writing the temporary Clang module cache and backend health is blocked by
sandbox loopback denial.

`./tests/smoke/smoke.sh` cannot connect to `127.0.0.1:8765` in this sandbox.

## Integration Deferred

The refreshed badge evidence is prepared on
`docs/agent-user-status-sladge-current` and is not merged into the canonical
checkout in this pass.
