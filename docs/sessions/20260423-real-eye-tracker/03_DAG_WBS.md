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
   - shared native/CLI evaluation counters. Done.
   - per-target accepted/rejected sample counts. Done.
   - stale/repeated sample rejection. CLI confidence-settle reasons done;
     native stale/low-confidence/unreliable counters done; repeated/stuck sample
     detection done.
   - projection-hold rejection metrics. CLI hold-candidate counts done.
   - coordinate parity tests,
   - stronger calibration collection/model upgrade.
14. Build the app-packaging/discoverability lane:
   - macOS `.app` bundle with `Info.plist`, icon, entitlements, and app identity.
     Done for local install bundle without icon/signing.
   - update LaunchAgent tray launch to app-bundle executable or intentional
     `open -a` flow. Done with direct app-bundle executable launch.
   - macOS `.pkg` dry-run packaging with signing/notarization hooks. Metadata
     scaffold and build helper done; signing/notarization remain opt-in release
     inputs.
   - Windows WinUI 3/MSIX manifest plan and installer scaffold. Done.
   - Linux GTK4/libadwaita `.desktop` and AppStream scaffold. Done.
15. Build the scoped sponsor/user messaging lane:
   - first-class recipient roles for `koosha` and `sponsor`. Done.
   - no arbitrary contact/search/send APIs. Done.
   - sync notify, async inbox, and wait APIs across CLI/MCP. Done.
   - redacted status by default with explicit local debug escape hatch only. Done.
16. Build the agent-session bus lane:
   - `session-scan` command for process tree, TTY, repo/cwd hints, and tmux
     metadata. Done; full cwd is opt-in with `--include-cwd`.
   - `POST /session/heartbeat`, `GET /sessions`, and `POST /event`. Done.
   - in-memory event ring plus schema-versioned JSONL. Done.
   - hook/subagent spawn/close event publishing. Stop-hook event publishing done;
     subagent spawn/close requires wrapper integration.
   - policy guidance for when to text versus use subagents. Done in long-term
     architecture guidance.
17. Build the quality-gate lane:
   - close current Ruff findings. Done.
   - close current Pyright findings. Done.
   - enable lint/type CI gates after green. Done.
18. Build the modularity lane for files above the 350-line target after gates
   are stable.

Critical path:
- Governance template hardening blocks consistent review of privacy-sensitive
  telemetry and runtime changes.
- Packaging/runtime path centralization blocks reliable non-default install
  prefixes and doctor coverage.
- Subagent wrapper integration still blocks automatic spawn/close session events.
- Full release distribution still needs real signing identities, notarization
  credentials, icon assets, and final install-channel manifests.
