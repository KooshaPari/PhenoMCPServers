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
   - shared native/CLI evaluation counters. CLI done; native parity pending.
   - per-target accepted/rejected sample counts. CLI done.
   - stale/repeated sample rejection. CLI confidence-settle reasons done;
     native stale counters already present; deeper repeated-sample detection pending.
   - projection-hold rejection metrics. CLI hold-candidate counts done.
   - coordinate parity tests,
   - stronger calibration collection/model upgrade.
14. Build the app-packaging/discoverability lane:
   - macOS `.app` bundle with `Info.plist`, icon, entitlements, and app identity.
     Metadata scaffold done; actual app bundle build pending.
   - update LaunchAgent tray launch to app-bundle executable or intentional
     `open -a` flow,
   - macOS `.pkg` dry-run packaging with signing/notarization hooks. Metadata
     scaffold done; build script pending.
   - Windows WinUI 3/MSIX manifest plan and installer scaffold. Done.
   - Linux GTK4/libadwaita `.desktop` and AppStream scaffold. Done.
15. Build the scoped sponsor/user messaging lane:
   - first-class recipient roles for `koosha` and `sponsor`. Done.
   - no arbitrary contact/search/send APIs. Done.
   - sync notify, async inbox, and wait APIs across CLI/MCP. Done.
   - redacted status by default with explicit local debug escape hatch only. Done.
16. Build the agent-session bus lane:
   - `session-scan` command for process tree, TTY, cwd, repo, and tmux metadata,
   - `POST /session/heartbeat`, `GET /sessions`, and `POST /event`. Done.
   - in-memory event ring plus schema-versioned JSONL. JSONL done; ring pending.
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
- App bundle build scripts and LaunchAgent app-bundle launch still block
  Spotlight-grade macOS runtime discoverability.
- Session scan and hook event publishing still block reliable process-to-session
  attachment and subagent/session coordination.
- Eye-tracker evaluation counters block clear diagnosis of model noise versus
  calibration failure versus intentional look-away.
- Lint/type cleanup blocks enabling stricter CI quality gates.
