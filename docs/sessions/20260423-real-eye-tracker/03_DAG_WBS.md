# DAG / WBS

1. Confirm GitHub auth and remote target. Done.
2. Create or attach the `origin` remote. Done.
3. Add session docs scaffold. Done.
4. Commit the initial repo state. Done.
5. Push to GitHub. Done.
6. Add backend privacy smoke checks in CI. Done in PR #1.
7. Fix native gaze coordinate parity. Done in PR #1.
8. Merge PR #1 after owned CI checks pass. Done.
9. Require both `unit-tests` and `backend-smoke` in branch protection. Done.
10. Extend governance templates with structured telemetry/privacy checklist. Done.
11. Add a dedicated security-report path and expand `SECURITY.md` handling steps. Done.
12. Build the packaging/runtime lane:
   - centralized executable path resolution. Done.
   - installed plist validation in doctor. Done.
   - documented environment override matrix. Done.
13. Build the next eye-tracker quality lane:
   - shared native/CLI evaluation counters,
   - per-target accepted/rejected sample counts,
   - stale/repeated sample rejection,
   - projection-hold rejection metrics,
   - coordinate parity tests,
   - stronger calibration collection/model upgrade.
14. Build the app-packaging/discoverability lane:
   - macOS `.app` bundle with `Info.plist`, icon, entitlements, and app identity,
   - update LaunchAgent tray launch to app-bundle executable or intentional
     `open -a` flow,
   - macOS `.pkg` dry-run packaging with signing/notarization hooks,
   - Windows WinUI 3/MSIX manifest plan and installer scaffold,
   - Linux GTK4/libadwaita `.desktop` and AppStream scaffold.
15. Build the scoped sponsor/user messaging lane:
   - first-class recipient roles for `koosha` and `sponsor`,
   - no arbitrary contact/search/send APIs,
   - sync notify, async inbox, and wait APIs across CLI/MCP,
   - redacted status by default with explicit local debug escape hatch only.
16. Build the agent-session bus lane:
   - `session-scan` command for process tree, TTY, cwd, repo, and tmux metadata,
   - `POST /session/heartbeat`, `GET /sessions`, and `POST /event`,
   - in-memory event ring plus schema-versioned JSONL,
   - hook/subagent spawn/close event publishing,
   - policy guidance for when to text versus use subagents.
17. Build the quality-gate lane:
   - close current Ruff findings,
   - close current Pyright findings,
   - enable lint/type CI gates after green.
18. Build the modularity lane for files above the 350-line target after gates
   are stable.

Critical path:
- Governance template hardening blocks consistent review of privacy-sensitive
  telemetry and runtime changes.
- Packaging/runtime path centralization blocks reliable non-default install
  prefixes and doctor coverage.
- App bundle identity blocks Spotlight/Start Menu/app-grid discoverability.
- Scoped recipient roles block polished sponsor/user messaging without contact
  sprawl.
- Agent session registry blocks reliable process-to-session attachment and
  subagent/session coordination.
- Eye-tracker evaluation counters block clear diagnosis of model noise versus
  calibration failure versus intentional look-away.
- Lint/type cleanup blocks enabling stricter CI quality gates.
