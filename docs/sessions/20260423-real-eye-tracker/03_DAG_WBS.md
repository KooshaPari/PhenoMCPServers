# DAG / WBS

1. Confirm GitHub auth and remote target. Done.
2. Create or attach the `origin` remote. Done.
3. Add session docs scaffold. Done.
4. Commit the initial repo state. Done.
5. Push to GitHub. Done.
6. Add backend privacy smoke checks in CI. Done locally; pending PR check.
7. Fix native gaze coordinate parity. Done locally.
8. Merge PR #1 after owned CI checks pass.
9. Require both `CI / unit-tests` and `CI / backend-smoke` in branch protection.
10. Extend governance templates with structured telemetry/privacy checklist.
11. Add a dedicated security-report path and expand `SECURITY.md` handling steps.
12. Build the next eye-tracker quality lane:
   - shared native/CLI evaluation counters,
   - per-target accepted/rejected sample counts,
   - stale/repeated sample rejection,
   - projection-hold rejection metrics,
   - coordinate parity tests,
   - stronger calibration collection/model upgrade.
13. Build the packaging/runtime lane:
   - centralized executable path resolution,
   - installed plist validation in doctor,
   - documented environment override matrix.
14. Build the quality-gate lane:
   - close current Ruff findings,
   - close current Pyright findings,
   - enable lint/type CI gates after green.
15. Build the modularity lane for files above the 350-line target after gates
   are stable.

Critical path:
- PR merge blocks branch-protection enforcement.
- Backend smoke stability blocks treating privacy regression coverage as
  required.
- Coordinate parity blocks trusting tray evaluation error metrics.
- Lint/type cleanup blocks enabling stricter CI quality gates.
