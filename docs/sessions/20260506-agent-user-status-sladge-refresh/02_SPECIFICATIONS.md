# Specifications

## Requirement

The active Agent User Status branch must disclose agent-oriented runtime
ownership with the Sladge badge near the README title.

## Acceptance Criteria

- `README.md` contains `https://sladge.net/badge.svg`.
- The change is prepared in `agent-user-status-wtrees/sladge-current`.
- Validation includes diff hygiene, README badge proof, and repo-local checks.

## ARUs

- Assumption: Badge-only documentation work does not require live service
  startup.
- Risk: Doctor/smoke checks can be blocked by sandbox loopback permissions.
- Mitigation: Run the checks, record the blocker, and avoid changing runtime
  install or LaunchAgent state.
